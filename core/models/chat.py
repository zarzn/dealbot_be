from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class ChatResponse(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    created_at: datetime = None

    class Config:
        from_attributes = True 