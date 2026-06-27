from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr

class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    email: str
    created_at: datetime
    
    model_config = {"from_attributes": True}

class CompanionCreate(BaseModel):
    name: str
    gender: Optional[str] = "unspecified"
    persona_type: str = "friend"

class CompanionResponse(BaseModel):
    companion_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    gender: str
    persona_type: str
    dynamic_attributes: dict
    created_at: datetime

    model_config = {"from_attributes": True}

class ChatHistoryResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
    
    model_config = {"from_attributes": True}
