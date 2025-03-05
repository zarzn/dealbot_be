"""Deal Token model module.

This module defines the token-related models for deals in the AI Agentic Deals System.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from core.models.base import Base
from core.models.enums import TokenStatus

class DealToken(Base):
    """Token model for deal tokens."""
    __tablename__ = "deal_tokens"
    __table_args__ = (
        Index('ix_deal_tokens_deal_id', 'deal_id'),
        Index('ix_deal_tokens_user_id', 'user_id'),
        {'extend_existing': True}
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id = Column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    symbol = Column(String(10), nullable=False)
    status = Column(SQLEnum(TokenStatus, values_callable=lambda x: [e.value.lower() for e in x]), nullable=False, default=TokenStatus.ACTIVE)
    token_metadata = Column(JSONB(astext_type=Text()))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    
    # Relationships
    deal = relationship("Deal", back_populates="tokens")
    user = relationship("User", back_populates="deal_tokens", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<DealToken {self.symbol} for deal {self.deal_id}>" 