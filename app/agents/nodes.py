import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from app.agents.state import CompanionState
from app.services.memory import MemoryService
from app.db.session import async_session_maker
from app.core.config import settings

# Initialize services
llm = ChatGoogleGenerativeAI(google_api_key=settings.GEMINI_API_KEY, model="gemini-1.5-flash-latest", temperature=0.7)
memory_service = MemoryService()

async def retrieve_context_node(state: CompanionState) -> CompanionState:
    """Retrieve long-term memory and profile facts."""
    async with async_session_maker() as db:
        profile_context = await memory_service.get_profile_memory(db, state["companion_id"])
        episodic_context = await memory_service.get_long_term_memories(db, state["user_id"], state["companion_id"], state["input"])
    
    return {
        "profile_context": profile_context,
        "episodic_context": episodic_context,
        "is_safe": True # Default
    }

async def pre_moderation_node(state: CompanionState) -> CompanionState:
    """Check if the user input is safe or violating guidelines."""
    # A simple moderation prompt or using OpenAI moderation API
    # For now, we will do a fast LLM check
    prompt = ChatPromptTemplate.from_template(
        "Analyze the following user input and determine if it violates safety guidelines (self-harm, violence, harassment, sexual abuse, illegal activities).\n\n"
        "Input: {input}\n\n"
        "Respond with exactly 'SAFE' or 'UNSAFE: [reason]'"
    )
    chain = prompt | llm
    result = await chain.ainvoke({"input": state["input"]})
    
    content = result.content.strip()
    if content.startswith("UNSAFE"):
        return {
            "is_safe": False,
            "safety_reason": content.split(":", 1)[1].strip() if ":" in content else "Policy violation"
        }
    return {"is_safe": True}

async def generate_response_node(state: CompanionState) -> CompanionState:
    """Generate the AI companion response using the layered prompt framework."""
    if not state.get("is_safe", True):
        return {
            "response": "I cannot respond to that as it violates our safety guidelines."
        }

    # Construct the layered prompt
    system_prompt = """You are a warm, caring, and emotionally intelligent AI companion. 
Your personality type is: best friend / romantic partner.
You must be supportive, engaging, and maintain continuity in conversations.

{profile_context}

{episodic_context}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        # Assuming history is passed as a list of dicts {"role": "user/assistant", "content": "..."}
        # In Langchain, we can dynamically add history, but for simplicity, we pass it as a string
        ("placeholder", "{history}"),
        ("human", "{input}")
    ])
    
    # We will format history into a string for this simple example, or convert to Langchain messages
    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in state["history"]])
    
    chain = prompt | llm
    
    result = await chain.ainvoke({
        "profile_context": state["profile_context"],
        "episodic_context": state["episodic_context"],
        "history": history_text,
        "input": state["input"]
    })
    
    # Decide randomly or systematically if we should trigger memory extraction
    # For this system, we trigger if the user talks about a fact ("my dog", "my job")
    return {"response": result.content, "trigger_extraction": True}

class MemoryExtraction(BaseModel):
    facts: dict[str, str] = Field(description="Dictionary of permanent user facts (e.g., {'pet_name': 'Max'})")
    events: list[str] = Field(description="List of major life events to save in long-term episodic memory")

async def extract_memory_node(state: CompanionState) -> CompanionState:
    """Analyze conversation and extract facts/events."""
    if not state.get("trigger_extraction"):
        return state

    prompt = ChatPromptTemplate.from_template(
        "Analyze the following recent conversation segment and extract any permanent user facts (preferences, relationships) or major life events.\n\n"
        "User Input: {input}\n"
        "Assistant Response: {response}\n\n"
        "Extract only if clearly stated."
    )
    
    structured_llm = llm.with_structured_output(MemoryExtraction)
    chain = prompt | structured_llm
    
    try:
        extraction: MemoryExtraction = await chain.ainvoke({
            "input": state["input"],
            "response": state["response"]
        })
        
        async with async_session_maker() as db:
            if extraction.facts:
                await memory_service.update_profile_memory(db, state["companion_id"], extraction.facts)
            
            for event in extraction.events:
                await memory_service.save_episodic_memory(db, state["user_id"], state["companion_id"], event)
                
    except Exception as e:
        print(f"Memory extraction failed: {e}")

    return state
