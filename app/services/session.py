import redis.asyncio as redis
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Ensure Upstash URLs strictly use TLS (rediss://)
redis_url = settings.REDIS_URL
if "upstash.io" in redis_url and redis_url.startswith("redis://"):
    redis_url = redis_url.replace("redis://", "rediss://", 1)

ssl_args = {"ssl_cert_reqs": "none"} if redis_url.startswith("rediss://") else {}
redis_client = redis.from_url(redis_url, decode_responses=True, **ssl_args)

# In-memory fallback just in case Redis fails (extremely resilient)
_fallback_cache = {}

class SessionManager:
    @staticmethod
    async def get_session(user_id: str, companion_id: str) -> dict:
        key = f"session:{user_id}:{companion_id}"
        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}. Using fallback memory.")
            if key in _fallback_cache:
                return _fallback_cache[key]
                
        return {"status": "active", "history": []}

    @staticmethod
    async def save_session(user_id: str, companion_id: str, session_data: dict):
        key = f"session:{user_id}:{companion_id}"
        try:
            await redis_client.set(key, json.dumps(session_data), ex=86400)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}. Using fallback memory.")
            _fallback_cache[key] = session_data

    @staticmethod
    async def add_message_to_history(user_id: str, companion_id: str, role: str, content: str):
        session = await SessionManager.get_session(user_id, companion_id)
        history = session.get("history", [])
        history.append({"role": role, "content": content})
        
        if len(history) > 15:
            history = history[-15:]
            
        session["history"] = history
        await SessionManager.save_session(user_id, companion_id, session)

    @staticmethod
    async def clear_session(user_id: str, companion_id: str):
        key = f"session:{user_id}:{companion_id}"
        try:
            await redis_client.delete(key)
        except Exception:
            _fallback_cache.pop(key, None)
