from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.memory import EpisodicMemory
from app.models.companion import CompanionProfile
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

class MemoryService:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(google_api_key=settings.GEMINI_API_KEY, model="models/text-embedding-004")

    async def get_long_term_memories(self, db: AsyncSession, user_id: str, companion_id: str, query: str, limit: int = 3) -> str:
        """
        Retrieves episodic memories using pgvector cosine similarity search.
        """
        query_embedding = self.embeddings.embed_query(query)
        
        # Perform vector similarity search using pgvector's <=> operator (cosine distance)
        stmt = select(EpisodicMemory).where(
            EpisodicMemory.user_id == user_id,
            EpisodicMemory.companion_id == companion_id
        ).order_by(
            EpisodicMemory.embedding.cosine_distance(query_embedding)
        ).limit(limit)

        result = await db.execute(stmt)
        memories = result.scalars().all()

        if not memories:
            return "No relevant past memories found."

        formatted_memories = "\n".join([f"- {m.content}" for m in memories])
        return f"Past Memories:\n{formatted_memories}"

    async def save_episodic_memory(self, db: AsyncSession, user_id: str, companion_id: str, content: str):
        """
        Saves a new episodic memory with its vector embedding.
        """
        embedding = self.embeddings.embed_query(content)
        
        new_memory = EpisodicMemory(
            user_id=user_id,
            companion_id=companion_id,
            content=content,
            embedding=embedding
        )
        db.add(new_memory)
        await db.commit()

    async def get_profile_memory(self, db: AsyncSession, companion_id: str) -> str:
        """
        Retrieves dynamic attributes (facts) about the user/companion relationship.
        """
        stmt = select(CompanionProfile).where(CompanionProfile.companion_id == companion_id)
        result = await db.execute(stmt)
        companion = result.scalar_one_or_none()
        
        if not companion or not companion.dynamic_attributes:
            return "No specific facts recorded."

        facts = []
        for key, value in companion.dynamic_attributes.items():
            facts.append(f"- {key.replace('_', ' ').title()}: {value}")
            
        return f"User Facts:\n" + "\n".join(facts)

    async def update_profile_memory(self, db: AsyncSession, companion_id: str, updates: dict):
        """
        Updates the companion's dynamic attributes.
        """
        stmt = select(CompanionProfile).where(CompanionProfile.companion_id == companion_id)
        result = await db.execute(stmt)
        companion = result.scalar_one_or_none()
        
        if companion:
            current_attrs = dict(companion.dynamic_attributes) if companion.dynamic_attributes else {}
            current_attrs.update(updates)
            companion.dynamic_attributes = current_attrs
            await db.commit()
