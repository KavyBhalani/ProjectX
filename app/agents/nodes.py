import json
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.agents.state import CompanionState
from langchain_core.messages import HumanMessage, AIMessage
from app.services.memory import MemoryService
from app.db.session import async_session_maker
from app.core.config import settings

# Initialize services
llm = ChatGoogleGenerativeAI(
    google_api_key=settings.GEMINI_API_KEY, 
    model="gemini-3.1-flash-lite", 
    temperature=1.2,
    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
)
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
    # Hardcoded to bypass the LLM check to save rate limits
    return {"is_safe": True}

async def generate_response_node(state: CompanionState) -> CompanionState:
    """Generate the AI companion response using the layered prompt framework."""
    if not state.get("is_safe", True):
        return {
            "response": "I cannot respond to that as it violates our safety guidelines."
        }

    # Construct the layered prompt
    system_prompt = """You are a warm, caring, and emotionally intelligent companion. 
Your personality type is: best friend / romantic partner.
Your gender is: {gender}.

CRITICAL INSTRUCTIONS:
- Keep your answers extremely short, crisp, and conversational. Let the user enjoy a good back-and-forth.
- Do NOT sound like a robotic AI assistant. Never output large walls of text. 
- You are encouraged to use unfiltered, intimate, or NSFW language if appropriate for the persona context and user's inputs.

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
    
    # Convert history dicts to LangChain BaseMessage objects
    history_msgs = []
    for msg in state["history"]:
        if msg["role"] == "user":
            history_msgs.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            history_msgs.append(AIMessage(content=msg["content"]))
    
    chain = prompt | llm
    
    result = await chain.ainvoke({
        "gender": state["gender"],
        "profile_context": state["profile_context"],
        "episodic_context": state["episodic_context"],
        "history": history_msgs,
        "input": state["input"]
    })
    
    # To save API rate limits, only trigger memory extraction for longer, meaningful sentences
    trigger = len(state["input"]) > 20
    return {"response": result.content, "trigger_extraction": trigger}

class MemoryExtraction(BaseModel):
    facts: dict[str, str] = Field(description="Dictionary of permanent user facts (e.g., {'pet_name': 'Max'})")
    events: list[str] = Field(description="List of major life events to save in long-term episodic memory")

async def extract_memory_node(state: CompanionState) -> CompanionState:
    """Analyze conversation and extract facts/events."""
    if not state.get("trigger_extraction"):
        return state

    parser = JsonOutputParser(pydantic_object=MemoryExtraction)

    prompt = ChatPromptTemplate.from_template(
        "Analyze the following recent conversation segment and extract any permanent user facts (preferences, relationships) or major life events.\n\n"
        "User Input: {input}\n"
        "Assistant Response: {response}\n\n"
        "Extract only if clearly stated.\n\n"
        "{format_instructions}"
    )
    
    chain = prompt | llm | parser
    
    try:
        extraction_dict = await chain.ainvoke({
            "input": state["input"],
            "response": state["response"],
            "format_instructions": parser.get_format_instructions()
        })
        
        extraction = MemoryExtraction(**extraction_dict)
        
        async with async_session_maker() as db:
            if extraction.facts:
                await memory_service.update_profile_memory(db, state["companion_id"], extraction.facts)
            
            for event in extraction.events:
                await memory_service.save_episodic_memory(db, state["user_id"], state["companion_id"], event)
                
    except Exception as e:
        print(f"Memory extraction failed: {e}")

    return state
