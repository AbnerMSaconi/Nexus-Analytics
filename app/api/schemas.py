from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str
    area: Optional[str] = "Geral"


class ConversationOut(BaseModel):
    id: str
    title: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    external_id: str
    full_name: str
    password: str = Field(..., min_length=4, max_length=50)
    role: str = "aluno"

class UserLogin(BaseModel):
    external_id: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
