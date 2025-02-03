"""Token balance model.

This module defines the TokenBalance model for tracking user token balances.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, String, DECIMAL, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import expression

from ..database import Base

class TokenBalance(Base):
    """Model for tracking user token balances."""
    
    __tablename__ = "token_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=expression.text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    balance = Column(DECIMAL(precision=18, scale=8), nullable=False, default=Decimal("0"))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=expression.text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=expression.text("now()"), onupdate=expression.text("now()"))

    def __repr__(self) -> str:
        """String representation of the token balance."""
        return f"<TokenBalance(user_id={self.user_id}, balance={self.balance})>" 