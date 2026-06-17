from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.endpoints import router
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import engine, Base
    from sqlalchemy import text
    from app.models.user import UserProfile
    from app.models.companion import CompanionProfile
    from app.models.chat import ChatLog
    from app.models.memory import EpisodicMemory
    
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables (useful if migrations aren't strictly managed yet)
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Allow CORS for frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def health_check():
    return JSONResponse(content={"status": "Production API is running", "version": settings.VERSION})
