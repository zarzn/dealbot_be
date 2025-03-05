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
from decimal import Decimal, ROUND_DOWN
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column, String, DateTime, Numeric, Enum as SQLEnum, text, ForeignKey, 
    Index, CheckConstraint, DECIMAL, case, func, select
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, expression
from core.models.base import Base
from core.models.enums import TransactionType
from core.exceptions import (
    ValidationError,
    InvalidBalanceChangeError,
    TokenBalanceError
)

class TokenBalanceHistoryBase(BaseModel):
    user_id: UUID
    balance_before: Decimal = Field(..., ge=0)
    balance_after: Decimal = Field(..., ge=0)
    change_amount: Decimal = Field(..., gt=0)
    change_type: TransactionType
    reason: str = Field(..., min_length=1, max_length=255)

    @field_validator('balance_after')
    @classmethod
    def validate_balance_after(cls, v: Decimal, info) -> Decimal:
        # Handle ValidationInfo object in Pydantic v2
        data = getattr(info, 'data', {})
        
        if 'balance_before' in data and 'change_amount' in data and 'change_type' in data:
            balance_before = Decimal(str(data['balance_before'])).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            change_amount = Decimal(str(data['change_amount'])).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            v = Decimal(str(v)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            
            if data['change_type'] == TransactionType.DEDUCTION:
                expected_balance = balance_before - change_amount
            else:
                expected_balance = balance_before + change_amount
            
            expected_balance = expected_balance.quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            
            if v != expected_balance:
                raise InvalidBalanceChangeError(f"Balance after ({v}) does not match expected value ({expected_balance})")
        return v

    @field_validator('balance_before', 'balance_after', 'change_amount')
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        return Decimal(str(v)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

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
        CheckConstraint('change_amount > 0', name='ch_nonzero_change'),
        CheckConstraint(
            """
            (
                change_type = 'deduction' AND 
                balance_after = balance_before - change_amount
            ) OR (
                change_type IN ('reward', 'refund', 'credit') AND 
                balance_after = balance_before + change_amount
            )
            """,
            name='ch_balance_change_match'
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_balance_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("token_balances.id", ondelete="CASCADE"), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    change_type: Mapped[str] = mapped_column(SQLEnum(TransactionType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    transaction_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("token_transactions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    user = relationship("User", back_populates="token_balance_history", lazy="selectin")
    token_balance = relationship("TokenBalance", back_populates="history", lazy="selectin")
    transaction = relationship("TokenTransaction", back_populates="balance_history", lazy="selectin")

    def __init__(self, **kwargs):
        """Initialize token balance history with validation."""
        if isinstance(kwargs.get('change_type'), TransactionType):
            kwargs['change_type'] = kwargs['change_type'].value

        # Validate balance changes
        if kwargs['change_type'] == TransactionType.DEDUCTION.value:
            # Use absolute value for deductions since change_amount could be passed as negative
            change_amount = abs(kwargs['change_amount'])
            if kwargs['balance_after'] != kwargs['balance_before'] - change_amount:
                raise ValueError("Invalid balance change for deduction")
        elif kwargs['change_type'] in [TransactionType.REWARD.value, TransactionType.REFUND.value, TransactionType.CREDIT.value]:
            # Ensure change_amount is positive for additions
            change_amount = abs(kwargs['change_amount'])
            if kwargs['balance_after'] != kwargs['balance_before'] + change_amount:
                raise ValueError("Invalid balance change for reward/refund/credit")

        # Store the absolute value of change_amount
        if kwargs['change_type'] == TransactionType.DEDUCTION.value and kwargs['change_amount'] < 0:
            kwargs['change_amount'] = abs(kwargs['change_amount'])

        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<TokenBalanceHistory(id={self.id}, type={self.change_type}, amount={self.change_amount})>"

    @classmethod
    async def create(cls, db, **kwargs) -> 'TokenBalanceHistory':
        """Create a new balance history record with proper validation"""
        try:
            # Ensure decimal precision
            for field in ['balance_before', 'balance_after', 'change_amount']:
                if field in kwargs:
                    kwargs[field] = Decimal(str(kwargs[field])).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            
            if isinstance(kwargs.get('change_type'), TransactionType):
                kwargs['change_type'] = kwargs['change_type'].value
            
            # Validate balance changes
            if kwargs['change_type'] == TransactionType.DEDUCTION.value:
                expected_after = (kwargs['balance_before'] - kwargs['change_amount']).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            else:
                expected_after = (kwargs['balance_before'] + kwargs['change_amount']).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            
            if kwargs['balance_after'] != expected_after:
                raise InvalidBalanceChangeError(f"Balance after ({kwargs['balance_after']}) does not match expected value ({expected_after})")
            
            history = cls(**kwargs)
            db.add(history)
            await db.flush()
            return history
        except Exception as e:
            raise ValueError(f"Failed to create balance history: {str(e)}") from e

    @classmethod
    async def get_by_user(cls, db, user_id: UUID) -> list['TokenBalanceHistory']:
        """Get all balance history records for a user"""
        stmt = select(cls).where(cls.user_id == user_id).order_by(cls.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def get_last_balance(cls, db, user_id: UUID) -> Optional['TokenBalanceHistory']:
        """Get the most recent balance history record for a user"""
        stmt = select(cls).where(cls.user_id == user_id).order_by(cls.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

class TokenBalanceHistoryResponse(BaseModel):
    """Schema for token balance history response"""
    id: UUID
    user_id: UUID
    balance_before: Decimal
    balance_after: Decimal
    change_amount: Decimal
    change_type: str
    reason: str
    created_at: datetime
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
