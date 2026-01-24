from pydantic import BaseModel
from typing import Optional, List, Dict

class ChatRequest(BaseModel):
    message: str
    area: Optional[str] = None  # Novo campo para identificar o especialista