"""Token Transaction model module.

This module defines the TokenTransaction model and related Pydantic schemas for tracking
token transactions in the AI Agentic Deals System.

Classes:
    TokenTransactionBase: Base Pydantic model for transaction data
    TokenTransactionCreate: Model for transaction creation
    TokenTransactionUpdate: Model for transaction updates
    TokenTransactionInDB: Model for database representation
    TokenTransaction: SQLAlchemy model for database table
"""

from uuid import UUID
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, DateTime, Numeric, Enum as SQLEnum, text, DECIMAL, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base
#from core.exceptions import InvalidTransactionError DO NOT DELETE THIS COMMENT

class TransactionType(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    REWARD = "reward"
    SEARCH_PAYMENT = "search_payment"
    SEARCH_REFUND = "search_refund"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class TokenTransactionBase(BaseModel):
    user_id: UUID
    type: TransactionType
    amount: float = Field(..., gt=0)
    status: TransactionStatus = TransactionStatus.PENDING
    tx_hash: Optional[str] = Field(
        None,
        min_length=66,
        max_length=66,
        pattern=r'^0x[a-fA-F0-9]{64}$'
    )

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be positive")
        return v

class TokenTransactionCreate(TokenTransactionBase):
    pass

class TokenTransactionUpdate(TokenTransactionBase):
    status: Optional[TransactionStatus] = None
    tx_hash: Optional[str] = Field(
        None,
        min_length=66,
        max_length=66,
        pattern=r'^0x[a-fA-F0-9]{64}$'
    )

class TokenTransactionInDB(TokenTransactionBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class TokenTransaction(Base):
    __tablename__ = 'tokentransaction'

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SQLEnum(TransactionType), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(precision=18, scale=8), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(precision=18, scale=8), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(precision=18, scale=8), nullable=False)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Blockchain transaction signature
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TokenTransaction(id={self.id}, type={self.type}, amount={self.amount})>"

    @classmethod
    async def create(cls, db, **kwargs) -> 'TokenTransaction':
        """Create a new token transaction with proper error handling"""
        try:
            transaction = cls(**kwargs)
            db.add(transaction)
            await db.commit()
            await db.refresh(transaction)
            return transaction
        except Exception as e:
            await db.rollback()
            raise ValueError(f"Failed to create transaction: {str(e)}") from e

    @classmethod
    async def get_by_user(cls, db, user_id: UUID) -> list['TokenTransaction']:
        """Get all transactions for a user"""
        return await db.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    async def update_status(
        cls,
        db,
        transaction_id: UUID,
        status: TransactionStatus,
        tx_hash: Optional[str] = None
    ) -> 'TokenTransaction':
        """Update transaction status with validation"""
        transaction = await db.query(cls).filter(cls.id == transaction_id).first()
        if not transaction:
            raise ValueError("Transaction not found")
            
        if tx_hash and not tx_hash.startswith('0x'):
            raise ValueError("Transaction hash must start with 0x")
            
        transaction.status = status
        if tx_hash:
            transaction.tx_hash = tx_hash
            
        await db.commit()
        await db.refresh(transaction)
        return transaction
