"""Token Balance History model module.

This module defines the TokenBalanceHistory model and related Pydantic schemas for tracking
token balance changes in the AI Agentic Deals System.

Classes:
    TokenBalanceHistoryBase: Base Pydantic model for balance history data
    TokenBalanceHistoryCreate: Model for balance history creation
    TokenBalanceHistoryInDB: Model for database representation
    TokenBalanceHistory: SQLAlchemy model for database table
"""

from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, DateTime, Numeric, Enum as SQLEnum, text, ForeignKey, Index, CheckConstraint, DECIMAL
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, expression
from core.models.base import Base
from core.exceptions import (
    ValidationError,
    InvalidBalanceChangeError,
    TokenBalanceError
)

class BalanceChangeType(str, Enum):
    """Balance change type enumeration."""
    DEDUCTION = "deduction"
    REWARD = "reward"
    REFUND = "refund"

class TokenBalanceHistoryBase(BaseModel):
    user_id: UUID
    balance_before: float = Field(..., ge=0)
    balance_after: float = Field(..., ge=0)
    change_amount: float = Field(..., gt=0)
    change_type: BalanceChangeType
    reason: str = Field(..., min_length=1, max_length=255)

    @field_validator('balance_after')
    @classmethod
    def validate_balance_after(cls, v: float, values: dict) -> float:
        if 'balance_before' in values:
            expected_balance = values['balance_before']
            if values['change_type'] == BalanceChangeType.DEDUCTION:
                expected_balance -= values['change_amount']
            else:
                expected_balance += values['change_amount']
            
            if abs(v - expected_balance) > 0.00000001:
                raise InvalidBalanceChangeError("Balance after does not match expected value")
        return v

class TokenBalanceHistoryCreate(TokenBalanceHistoryBase):
    pass

class TokenBalanceHistoryInDB(TokenBalanceHistoryBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class TokenBalanceHistory(Base):
    """Token balance history database model."""
    __tablename__ = "token_balance_history"
    __table_args__ = (
        Index('ix_token_balance_history_user', 'user_id'),
        Index('ix_token_balance_history_type', 'change_type'),
        CheckConstraint('change_amount != 0', name='ch_nonzero_change'),
        CheckConstraint('balance_after = balance_before + change_amount', name='ch_balance_change_match'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    change_type: Mapped[BalanceChangeType] = mapped_column(SQLEnum(BalanceChangeType), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("token_transactions.id"))

    # Relationships
    user = relationship("User", back_populates="balance_history")
    transaction = relationship("TokenTransaction", backref="balance_changes")

    def __repr__(self):
        return f"<TokenBalanceHistory {self.id}>"

    @classmethod
    async def create(cls, db, **kwargs) -> 'TokenBalanceHistory':
        """Create a new balance history record with proper validation"""
        try:
            history = cls(**kwargs)
            db.add(history)
            await db.commit()
            await db.refresh(history)
            return history
        except Exception as e:
            await db.rollback()
            raise ValueError(f"Failed to create balance history: {str(e)}") from e

    @classmethod
    async def get_by_user(cls, db, user_id: UUID) -> list['TokenBalanceHistory']:
        """Get all balance history records for a user"""
        return await db.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    async def get_last_balance(cls, db, user_id: UUID) -> Optional['TokenBalanceHistory']:
        """Get the most recent balance history record for a user"""
        return await db.query(cls)\
            .filter(cls.user_id == user_id)\
            .order_by(cls.created_at.desc())\
            .first()

class TokenBalanceHistoryResponse(BaseModel):
    """Schema for token balance history response"""
    id: UUID
    user_id: UUID
    balance_before: float
    balance_after: float
    change_amount: float
    change_type: str
    reason: str
    created_at: datetime
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
