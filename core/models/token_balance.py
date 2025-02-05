"""Token balance model module.

This module defines the TokenBalance model and related Pydantic schemas for tracking
user token balances in the AI Agentic Deals System.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
import logging

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, DECIMAL, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression, text

from core.models.base import Base
logger = logging.getLogger(__name__)

# Custom exception classes
class TokenBalanceError(Exception):
    """Base class for token balance-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class InsufficientBalanceError(TokenBalanceError):
    """Error raised when balance is insufficient."""
    pass

class InvalidBalanceError(TokenBalanceError):
    """Error raised when balance is invalid."""
    pass

class TokenBalanceBase(BaseModel):
    """Base token balance model."""
    user_id: UUID
    balance: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = Field(default=True)

    @validator('balance')
    @classmethod
    def validate_balance(cls, v: Decimal) -> Decimal:
        """Validate balance is non-negative.
        
        Args:
            v: Balance value to validate
            
        Returns:
            Decimal: The validated balance value
            
        Raises:
            InvalidBalanceError: If balance is negative
        """
        if v < 0:
            raise InvalidBalanceError("Balance cannot be negative")
        return v

class TokenBalanceCreate(TokenBalanceBase):
    """Schema for creating a token balance."""
    pass

class TokenBalanceUpdate(BaseModel):
    """Schema for updating a token balance."""
    balance: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None

class TokenBalanceResponse(TokenBalanceBase):
    """Schema for token balance response."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

class TokenBalance(Base):
    """Token balance database model."""
    __tablename__ = "tokenbalance"
    __table_args__ = (
        Index('ix_token_balances_user', 'user_id'),
        Index('ix_token_balances_active', 'is_active'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    balance: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=18, scale=8),
        nullable=False,
        default=Decimal("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )

    # Relationships
    user = relationship("User", back_populates="token_balance")
    history = relationship("TokenBalanceHistory", back_populates="token_balance", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the token balance."""
        return f"<TokenBalance(user_id={self.user_id}, balance={self.balance})>"

    async def update_balance(
        self,
        db: AsyncSession,
        amount: Decimal,
        operation: str = 'deduction'
    ) -> None:
        """Update token balance with validation.
        
        Args:
            db: Database session for transaction management
            amount: Amount to update
            operation: Type of operation ('deduction', 'reward', or 'refund')
            
        Raises:
            InvalidBalanceError: If operation type is invalid
            InsufficientBalanceError: If balance is insufficient for deduction
            TokenBalanceError: If update fails
        """
        try:
            if operation not in ['deduction', 'reward', 'refund']:
                raise InvalidBalanceError("Invalid operation type")

            if operation == 'deduction':
                if self.balance < amount:
                    raise InsufficientBalanceError(
                        f"Insufficient balance. Required: {amount}, Available: {self.balance}"
                    )
                self.balance -= amount
            else:
                self.balance += amount

            self.updated_at = datetime.utcnow()
            await db.commit()

            logger.info(
                f"Updated token balance",
                extra={
                    'user_id': str(self.user_id),
                    'operation': operation,
                    'amount': str(amount),
                    'new_balance': str(self.balance)
                }
            )

        except (InvalidBalanceError, InsufficientBalanceError) as e:
            await db.rollback()
            logger.error(
                f"Failed to update token balance",
                extra={
                    'user_id': str(self.user_id),
                    'operation': operation,
                    'amount': str(amount),
                    'error': str(e)
                }
            )
            raise

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to update token balance",
                extra={
                    'user_id': str(self.user_id),
                    'operation': operation,
                    'amount': str(amount),
                    'error': str(e)
                }
            )
            raise TokenBalanceError(f"Failed to update balance: {str(e)}")
