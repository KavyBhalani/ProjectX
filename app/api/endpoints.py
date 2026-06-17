from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.services.session import SessionManager
from app.agents.graph import companion_graph
from app.agents.state import CompanionState
from app.models.chat import ChatLog
from app.models.user import UserProfile
from app.models.companion import CompanionProfile
from app.schemas import UserCreate, UserResponse, CompanionCreate, CompanionResponse, ChatHistoryResponse
import json
import uuid
import asyncio

router = APIRouter()

# --- REST API Endpoints ---

@router.post("/api/users", response_model=UserResponse)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    stmt = select(UserProfile).where(UserProfile.email == user_in.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    new_user = UserProfile(username=user_in.username, email=user_in.email)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/api/users/{user_id}/companions", response_model=CompanionResponse)
async def create_companion(user_id: uuid.UUID, comp_in: CompanionCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
        
    new_comp = CompanionProfile(user_id=user_id, name=comp_in.name, persona_type=comp_in.persona_type)
    db.add(new_comp)
    await db.commit()
    await db.refresh(new_comp)
    return new_comp

@router.get("/api/users/{user_id}/companions", response_model=list[CompanionResponse])
async def list_companions(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(CompanionProfile).where(CompanionProfile.user_id == user_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/api/chat/{user_id}/{companion_id}/history", response_model=list[ChatHistoryResponse])
async def get_chat_history(user_id: uuid.UUID, companion_id: uuid.UUID, limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(ChatLog).where(
        ChatLog.user_id == user_id, 
        ChatLog.companion_id == companion_id
    ).order_by(ChatLog.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return logs[::-1] # Return chronological order


# --- WebSocket Endpoint ---

# Background task for memory extraction
async def run_memory_extraction(state: CompanionState):
    from app.agents.nodes import extract_memory_node
    # Only run the extraction node
    await extract_memory_node(state)

@router.websocket("/ws/chat/{user_id}/{companion_id}")
async def websocket_chat(websocket: WebSocket, user_id: str, companion_id: str, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    
    try:
        u_id = uuid.UUID(user_id)
        c_id = uuid.UUID(companion_id)
        
        # Verify existence
        comp_stmt = select(CompanionProfile).where(CompanionProfile.companion_id == c_id, CompanionProfile.user_id == u_id)
        result = await db.execute(comp_stmt)
        if not result.scalar_one_or_none():
            await websocket.send_json({"type": "error", "text": "Invalid User ID or Companion ID"})
            await websocket.close()
            return

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") != "message":
                continue
                
            user_input = message.get("text", "")
            
            # Save user message
            chat_log = ChatLog(user_id=u_id, companion_id=c_id, role="user", content=user_input)
            db.add(chat_log)
            await db.commit()
            
            # Get Session history
            session = await SessionManager.get_session(user_id, companion_id)
            history = session.get("history", [])
            
            # Setup State
            state = CompanionState(
                user_id=user_id,
                companion_id=companion_id,
                input=user_input,
                history=history,
                profile_context="",
                episodic_context="",
                is_safe=True,
                safety_reason=None,
                response="",
                trigger_extraction=False
            )
            
            # Invoke LangGraph (We modified the graph to NOT run extract_memory inline to save time!)
            # We will run the nodes manually to decouple extraction, or we modify the graph
            # For simplicity without breaking the graph structure, let's invoke it as is, 
            # OR we bypass the graph's extract_memory edge in graph.py.
            
            result = await companion_graph.ainvoke(state)
            response_text = result["response"]
            
            # Save assistant message
            chat_log_assist = ChatLog(user_id=u_id, companion_id=c_id, role="assistant", content=response_text)
            db.add(chat_log_assist)
            await db.commit()
            
            # Update Session History
            await SessionManager.add_message_to_history(user_id, companion_id, "user", user_input)
            await SessionManager.add_message_to_history(user_id, companion_id, "assistant", response_text)
            
            # Send response to client
            words = response_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                await websocket.send_json({"type": "token", "text": chunk})
                
            # Run memory extraction completely in the background!
            asyncio.create_task(run_memory_extraction(result))
                
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "text": f"Error: {str(e)}"})
        except:
            pass
