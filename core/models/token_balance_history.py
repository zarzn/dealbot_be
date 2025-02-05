"""Token Balance History model module.

This module defines the TokenBalanceHistory model and related Pydantic schemas for tracking
token balance changes in the AI Agentic Deals System.

Classes:
    TokenBalanceHistoryBase: Base Pydantic model for balance history data
    TokenBalanceHistoryCreate: Model for balance history creation
    TokenBalanceHistoryInDB: Model for database representation
    TokenBalanceHistory: SQLAlchemy model for database table
"""

from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, DateTime, Numeric, Enum as SQLEnum, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base
from core.exceptions import (
    ValidationError,
    InvalidBalanceChangeError,
    TokenBalanceError
)

class BalanceChangeType(str, Enum):
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
    __tablename__ = 'token_balance_history'

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    balance_before: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    change_amount: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    change_type: Mapped[BalanceChangeType] = mapped_column(SQLEnum(BalanceChangeType), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('NOW()'))

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
