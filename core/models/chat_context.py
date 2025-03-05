"""Chat context model module.

This module defines the chat context related models for the AI Agentic Deals System,
which store contextual information for chat conversations.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Index, ForeignKey, String, DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.models.base import Base

class ChatContext(Base):
    """Chat context database model."""
    __tablename__ = "chat_contexts"
    __table_args__ = (
        Index('ix_chat_contexts_user', 'user_id'),
        Index('ix_chat_contexts_conversation', 'conversation_id'),
        Index('ix_chat_contexts_expires', 'expires_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    context_type: Mapped[str] = mapped_column(String(50), nullable=False)
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("User", back_populates="chat_contexts")

    def __repr__(self) -> str:
        """String representation of the chat context."""
        return f"<ChatContext {self.context_type} for conversation {self.conversation_id}>" 