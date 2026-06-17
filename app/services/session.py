import redis.asyncio as redis
import json
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class SessionManager:
    @staticmethod
    async def get_session(user_id: str, companion_id: str) -> dict:
        key = f"session:{user_id}:{companion_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return {"status": "active", "history": []}

    @staticmethod
    async def save_session(user_id: str, companion_id: str, session_data: dict):
        key = f"session:{user_id}:{companion_id}"
        await redis_client.set(key, json.dumps(session_data), ex=86400) # Expire in 24 hours

    @staticmethod
    async def add_message_to_history(user_id: str, companion_id: str, role: str, content: str):
        session = await SessionManager.get_session(user_id, companion_id)
        history = session.get("history", [])
        history.append({"role": role, "content": content})
        
        # Keep only the last 15 messages for short-term memory
        if len(history) > 15:
            history = history[-15:]
            
        session["history"] = history
        await SessionManager.save_session(user_id, companion_id, session)

    @staticmethod
    async def clear_session(user_id: str, companion_id: str):
        key = f"session:{user_id}:{companion_id}"
        await redis_client.delete(key)
