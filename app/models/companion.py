import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base

class CompanionProfile(Base):
    __tablename__ = "companion_profiles"

    companion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    persona_type = Column(String(50), nullable=False, default="friend") # e.g., friend, romantic, mentor
    dynamic_attributes = Column(JSONB, default=dict) # To store facts, likes, dislikes
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", backref="companions")
