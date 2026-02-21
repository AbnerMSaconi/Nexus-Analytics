from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Schemas de Chat e Auth existentes ---

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
    course: Optional[str] = None # Adicionado caso queira registrar curso no signup

class UserLogin(BaseModel):
    external_id: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    course: Optional[str] = None

# --- NOVOS SCHEMAS PARA O PAINEL DE ADMINISTRAÇÃO ---

class UserResponse(BaseModel):
    id: str
    external_id: str
    full_name: Optional[str] = None
    role: str
    course: Optional[str] = None
    is_blocked: Optional[bool] = False 
    failed_attempts: Optional[int] = 0
    
    class Config:
        from_attributes = True

class UserRoleUpdate(BaseModel):
    role: str

class UserUpdate(BaseModel):
    external_id: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    course: Optional[str] = None
    password: Optional[str] = None  # Permite resetar a senha, se preenchido