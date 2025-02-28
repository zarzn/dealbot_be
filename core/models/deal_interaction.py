"""Deal interaction model module.

This module defines the DealInteraction model for tracking user interactions with deals.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Text, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression, text

from core.models.base import Base

class InteractionType:
    """Constants for interaction types."""
    VIEW = "view"
    SAVE = "save"
    SHARE = "share"
    CLICK = "click"
    PURCHASE = "purchase"
    BOOKMARK = "bookmark"
    FEEDBACK = "feedback"
    COMPARE = "compare"
    TRACK = "track"
    UNTRACK = "untrack"

class DealInteraction(Base):
    """Model for tracking user interactions with deals."""
    __tablename__ = "deal_interactions"
    __table_args__ = (
        Index('ix_deal_interactions_user_id', 'user_id'),
        Index('ix_deal_interactions_deal_id', 'deal_id'),
        Index('ix_deal_interactions_interaction_type', 'interaction_type'),
        Index('ix_deal_interactions_created_at', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    interaction_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    referrer: Mapped[Optional[str]] = mapped_column(Text)
    device_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('UTC', CURRENT_TIMESTAMP)")
    )
    is_conversion: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships - defined in relationships.py
    # user = relationship("User", back_populates="deal_interactions")
    # deal = relationship("Deal", back_populates="interactions")
    
    def __repr__(self) -> str:
        """String representation of the DealInteraction."""
        return f"<DealInteraction {self.interaction_type} on {self.deal_id} by {self.user_id}>" 