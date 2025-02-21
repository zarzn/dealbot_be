"""Token balance model module.

This module defines the TokenBalance model and related Pydantic schemas for tracking
user token balances in the AI Agentic Deals System.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
import logging

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DECIMAL, DateTime, ForeignKey, Boolean, Index, CheckConstraint, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.models.base import Base
from core.models.token_balance_history import TokenBalanceHistory, BalanceChangeType

logger = logging.getLogger(__name__)

# Custom exception classes
class TokenBalanceError(Exception):
    """Base class for token balance-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class InsufficientBalanceError(TokenBalanceError):
    """Raised when attempting to deduct more tokens than available."""
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        message = f"Insufficient balance for deduction. Required: {required}, Available: {available}"
        super().__init__(message)

class InvalidBalanceError(TokenBalanceError):
    """Raised when attempting an invalid balance operation."""
    pass

class TokenBalanceBase(BaseModel):
    """Base schema for token balance."""
    user_id: UUID
    balance: float = Field(ge=0)

    @field_validator('balance')
    @classmethod
    def validate_balance(cls, v: float) -> float:
        """Validate balance is non-negative."""
        if v < 0:
            raise InvalidBalanceError("Balance cannot be negative")
        return v

class TokenBalanceCreate(TokenBalanceBase):
    """Schema for creating a token balance."""
    pass

class TokenBalanceResponse(TokenBalanceBase):
    """Schema for token balance response."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TokenBalance(Base):
    """SQLAlchemy model for token_balances table"""
    __tablename__ = 'token_balances'
    __table_args__ = (
        Index('ix_token_balances_user_id', 'user_id'),
        CheckConstraint('balance >= 0', name='ch_positive_balance'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="token_balance_record",
        lazy="selectin"
    )
    history: Mapped[list["TokenBalanceHistory"]] = relationship(
        "TokenBalanceHistory",
        back_populates="token_balance",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of the token balance."""
        return "<TokenBalance(user_id={}, balance={})>".format(self.user_id, self.balance)

    async def update_balance(
        self,
        db: AsyncSession,
        amount: Decimal,
        operation: str = 'deduction',
        reason: str = None
    ) -> None:
        """Update token balance with validation and history tracking.
        
        Args:
            db: Database session for transaction management
            amount: Amount to update
            operation: Type of operation ('deduction', 'reward', or 'refund')
            reason: Description of the balance change reason
            
        Raises:
            InvalidBalanceError: If operation type is invalid
            InsufficientBalanceError: If balance is insufficient for deduction
            TokenBalanceError: If update fails
        """
        try:
            # Convert operation to lowercase and validate
            operation = operation.lower()
            if operation not in [op.value for op in BalanceChangeType]:
                raise InvalidBalanceError("Invalid operation type")

            # Store current balance for history
            balance_before = self.balance

            # Update balance based on operation
            if operation == BalanceChangeType.DEDUCTION.value:
                if self.balance < amount:
                    raise InsufficientBalanceError(required=amount, available=self.balance)
                self.balance -= amount
            else:
                self.balance += amount

            # Create balance history record
            history_record = TokenBalanceHistory(
                user_id=self.user_id,
                token_balance_id=self.id,
                balance_before=balance_before,
                balance_after=self.balance,
                change_amount=amount,
                change_type=operation,
                reason=reason or f"Token {operation}"
            )
            db.add(history_record)

            # Update timestamp
            self.updated_at = datetime.utcnow()

            # Commit changes
            await db.commit()
            await db.refresh(self)
            await db.refresh(history_record)

            logger.info(
                "Balance updated successfully",
                extra={
                    'user_id': str(self.user_id),
                    'operation': operation,
                    'amount': str(amount),
                    'balance_before': str(balance_before),
                    'balance_after': str(self.balance)
                }
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to update balance",
                extra={
                    'user_id': str(self.user_id),
                    'operation': operation,
                    'amount': str(amount),
                    'error': str(e)
                }
            )
            if isinstance(e, (InvalidBalanceError, InsufficientBalanceError)):
                raise
            raise TokenBalanceError(f"Failed to update balance: {str(e)}") from e
