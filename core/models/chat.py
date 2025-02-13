"""Chat model module.

This module defines the chat-related models for the AI Agentic Deals System,
including message types and response formats.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression

from core.models.base import Base
# Custom exception class
class ChatError(Exception):
    """Base class for chat-related errors."""
    pass

logger = logging.getLogger(__name__)

class ChatMessage(Base):
    """Chat message database model."""
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index('ix_chat_messages_user', 'user_id'),
        Index('ix_chat_messages_created', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.text('CURRENT_TIMESTAMP')
    )

    # Relationships
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self) -> str:
        """String representation of the chat message."""
        return f"<ChatMessage {self.role}: {self.content[:50]}...>"

class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message."""
    content: str = Field(..., min_length=1)
    role: str = Field(..., pattern="^(user|assistant|system)$")
    context: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate message role."""
        valid_roles = {'user', 'assistant', 'system'}
        if v not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v

class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: UUID
    user_id: UUID
    content: str
    role: str
    context: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatResponse(BaseModel):
    """Chat response model."""
    id: UUID
    user_id: UUID
    message: str
    role: str = Field(default="assistant")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[dict] = None
    tokens_used: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class ChatHistory(BaseModel):
    """Chat history model."""
    messages: List[ChatMessageResponse]
    total_tokens: int = 0
    
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    context: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)

class ChatAnalytics(BaseModel):
    """Chat analytics model."""
    total_messages: int
    messages_by_role: Dict[str, int]
    average_tokens_per_message: float
    total_tokens_used: int
    most_active_periods: List[Dict[str, Any]]
    common_topics: List[Dict[str, float]]
    response_times: Dict[str, float]
    user_engagement_metrics: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)

class ChatFilter(BaseModel):
    """Filter parameters for chat queries."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    role: Optional[str] = None
    search_query: Optional[str] = None
    min_tokens: Optional[int] = Field(None, ge=0)
    max_tokens: Optional[int] = Field(None, ge=0)
    context_type: Optional[str] = None
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    
    model_config = ConfigDict(from_attributes=True)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate message role if provided."""
        if v is not None:
            valid_roles = {'user', 'assistant', 'system'}
            if v not in valid_roles:
                raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        return v
    
    @field_validator('sort_by')
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        """Validate sort field."""
        valid_fields = {'created_at', 'tokens_used', 'role'}
        if v not in valid_fields:
            raise ValueError(f"Invalid sort field. Must be one of: {', '.join(valid_fields)}")
        return v
