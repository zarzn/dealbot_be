"""Token balance model module.

This module defines the TokenBalance model and related Pydantic schemas for tracking
user token balances in the AI Agentic Deals System.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import logging

from pydantic import BaseModel, Field, field_validator
import sqlalchemy as sa
from sqlalchemy import (
    Column, DECIMAL, DateTime, ForeignKey, Boolean, Index, 
    CheckConstraint, Numeric, text, select, and_
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func, expression

from core.models.base import Base
from core.models.enums import TransactionType
from core.models.token_balance_history import TokenBalanceHistory
from core.exceptions import InsufficientBalanceError

logger = logging.getLogger(__name__)

class TokenBalanceBase(BaseModel):
    """Base schema for token balance."""
    user_id: UUID
    balance: Decimal = Field(ge=0)

    @field_validator('balance')
    @classmethod
    def validate_balance(cls, v: Decimal) -> Decimal:
        """Validate balance is non-negative."""
        if v < 0:
            raise ValueError("Balance cannot be negative")
        return Decimal(str(v)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

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
    """Token balance model for tracking user token balances."""
    __tablename__ = "token_balances"
    __table_args__ = (
        CheckConstraint('balance >= 0', name='ch_positive_balance'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    balance: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
        default=Decimal('0').quantize(Decimal('0.00000000'), rounding=ROUND_DOWN),
        server_default=text("0.00000000")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

    # Relationships
    user = relationship("User", back_populates="token_balances")
    history = relationship("TokenBalanceHistory", back_populates="token_balance")

    def __repr__(self) -> str:
        return f"<TokenBalance(id={self.id}, balance={self.balance})>"

    @property
    def quantized_balance(self) -> Decimal:
        """Get balance with proper precision."""
        return Decimal(str(self.balance)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

    @quantized_balance.setter
    def quantized_balance(self, value: Decimal) -> None:
        """Set balance with proper precision."""
        self.balance = Decimal(str(value)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

    async def update_balance(
        self,
        db: AsyncSession,
        amount: Decimal,
        operation: str,
        reason: str,
        transaction_id: Optional[UUID] = None,
        transaction_data: Optional[Dict[str, Any]] = None
    ) -> 'TokenBalance':
        """Update token balance with proper validation and history tracking.
        
        Args:
            db: Database session
            amount: Amount to add/subtract
            operation: Operation type (deduction, reward, refund)
            reason: Reason for the balance change
            transaction_id: Optional related transaction ID
            transaction_data: Optional transaction metadata
            
        Returns:
            Updated token balance
            
        Raises:
            InsufficientBalanceError: If balance would become negative
            ValueError: If operation type is invalid
        """
        # Validate operation type
        if operation not in [e.value for e in TransactionType] and operation != 'credit':
            raise ValueError(f"Invalid operation type: {operation}")

        # Record old balance
        old_balance = self.quantized_balance

        # Ensure amount has proper precision
        amount = Decimal(str(amount)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

        # Calculate new balance based on operation
        if operation == TransactionType.DEDUCTION.value:
            if old_balance < amount:
                details = {"required": str(amount)}
                raise InsufficientBalanceError(
                    message="Insufficient balance for deduction",
                    available=old_balance,
                    details=details
                )
            new_balance = (old_balance - amount).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
        elif operation in [TransactionType.REWARD.value, TransactionType.REFUND.value, 'credit']:
            new_balance = (old_balance + amount).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
        else:
            raise ValueError(f"Invalid operation type: {operation}")

        # Update balance
        self.quantized_balance = new_balance

        # Create history record
        history = TokenBalanceHistory(
            user_id=self.user_id,
            token_balance_id=self.id,
            balance_before=old_balance,
            balance_after=new_balance,
            change_amount=amount,
            change_type=operation,
            reason=reason,
            transaction_id=transaction_id,
            transaction_data=transaction_data
        )
        db.add(history)

        try:
            await db.commit()
            await db.refresh(self)
            # Ensure balance is properly quantized after refresh
            self.quantized_balance = self.balance
            await db.flush()
            return self
        except Exception as e:
            await db.rollback()
            raise ValueError(f"Failed to update balance: {str(e)}") from e
