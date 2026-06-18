import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.session import Base

class EpisodicMemory(Base):
    __tablename__ = "episodic_memory"

    memory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.user_id", ondelete="CASCADE"), nullable=False)
    companion_id = Column(UUID(as_uuid=True), ForeignKey("companion_profiles.companion_id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(3072)) # Standard size for Google gemini-embedding-2
    created_at = Column(DateTime, default=datetime.utcnow)
