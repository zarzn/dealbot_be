"""Token Transaction model module.

This module defines the TokenTransaction model and related Pydantic schemas for tracking
token transactions in the AI Agentic Deals System.

Classes:
    TokenTransactionBase: Base Pydantic model for transaction data
    TokenTransactionCreate: Model for transaction creation
    TokenTransactionUpdate: Model for transaction updates
    TokenTransactionInDB: Model for database representation
    TokenTransaction: SQLAlchemy model for database table
    TransactionResponse: Model for transaction response
    TransactionHistoryResponse: Model for transaction history response
"""

from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Column, String, DateTime, Numeric, Enum as SQLEnum, text, DECIMAL, ForeignKey, JSON, Index, CheckConstraint, Integer, Text, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.base import Base
from core.models.enums import TransactionType, TransactionStatus, TokenTransactionType, TokenTransactionStatus

__all__ = [
    'TokenTransaction',
    'TokenTransactionCreate',
    'TokenTransactionUpdate',
    'TokenTransactionInDB',
    'TransactionType',
    'TransactionStatus',
    'TransactionResponse',
    'TransactionHistoryResponse'
]

class TokenTransactionBase(BaseModel):
    user_id: UUID
    type: str  # Changed from TransactionType to str to allow more flexible validation
    amount: float = Field(..., gt=0)
    status: TransactionStatus = TransactionStatus.PENDING
    tx_hash: Optional[str] = Field(
        None,
        min_length=66,
        max_length=66,
        pattern=r'^0x[a-fA-F0-9]{64}$'
    )

    @model_validator(mode='after')
    def validate_transaction(self) -> 'TokenTransactionBase':
        """Validate amount is positive and transaction type is valid."""
        if self.amount <= 0:
            raise ValueError("Transaction amount must be positive")
            
        # Validate the transaction type
        valid_types = set([t.value for t in TransactionType] + [t.value for t in TokenTransactionType])
        if self.type not in valid_types:
            raise ValueError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
            
        return self

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

class TransactionResponse(TokenTransactionInDB):
    balance_before: float
    balance_after: float
    details: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    updated_at: datetime
    completed_at: Optional[datetime] = None

class TransactionHistoryResponse(BaseModel):
    transactions: list[TransactionResponse]
    total_count: int
    total_pages: int
    current_page: int
    page_size: int

class TokenTransaction(Base):
    """Token transaction database model."""
    __tablename__ = "token_transactions"
    __table_args__ = (
        Index('ix_token_transactions_user_status', 'user_id', 'status'),
        CheckConstraint('amount > 0', name='ch_positive_amount'),
        {'extend_existing': True}
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(SQLEnum(TokenTransactionType, values_callable=lambda x: [e.value.lower() for e in x], name='transactiontype'), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), 
        nullable=False,
        default=Decimal('0').quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    )
    status: Mapped[str] = mapped_column(SQLEnum(TokenTransactionStatus, values_callable=lambda x: [e.value.lower() for e in x], name='transactionstatus'), nullable=False, default=TokenTransactionStatus.PENDING.value)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(66))
    block_number: Mapped[Optional[int]] = mapped_column(Integer)
    gas_used: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 8))
    gas_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 8))
    network_fee: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 8))
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_transactions", lazy="selectin")
    balance_history = relationship("TokenBalanceHistory", back_populates="transaction", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TokenTransaction(id={self.id}, type={self.type}, amount={self.amount})>"

    @property
    def quantized_amount(self) -> Decimal:
        """Get amount with proper precision."""
        return Decimal(str(self.amount)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

    @quantized_amount.setter
    def quantized_amount(self, value: Decimal) -> None:
        """Set amount with proper precision."""
        self.amount = Decimal(str(value)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

    def validate_amount(self) -> None:
        """Validate transaction amount."""
        if self.amount <= 0:
            raise ValueError("Transaction amount must be positive")
        self.quantized_amount = self.amount

    def validate_type(self) -> None:
        """Validate transaction type."""
        if self.type not in [t.value for t in TokenTransactionType]:
            raise ValueError(f"Invalid transaction type: {self.type}")

    def validate_status(self) -> None:
        """Validate transaction status."""
        if self.status not in [s.value for s in TokenTransactionStatus]:
            raise ValueError(f"Invalid transaction status: {self.status}")

    async def process(self, db: AsyncSession) -> None:
        """Process the transaction and update user balance."""
        from core.models.token_balance import TokenBalance
        
        # Validate transaction
        self.validate_amount()
        self.validate_type()
        self.validate_status()

        if self.status == TokenTransactionStatus.COMPLETED.value:
            # Get or create token balance
            stmt = select(TokenBalance).where(TokenBalance.user_id == self.user_id)
            result = await db.execute(stmt)
            token_balance = result.scalar_one_or_none()

            if not token_balance:
                # Ensure we have a valid user_id
                if not self.user_id and self.user:
                    self.user_id = self.user.id
                
                if not self.user_id:
                    raise ValueError("Cannot create token balance without user_id")

                token_balance = TokenBalance(
                    user_id=self.user_id,
                    balance=Decimal('0').quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
                )
                db.add(token_balance)
                await db.flush()

            # Update balance
            await token_balance.update_balance(
                db=db,
                amount=self.quantized_amount,
                operation=self.type,
                reason=f"{self.type.capitalize()} transaction",
                transaction_id=self.id,
                transaction_data=self.meta_data
            )

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
            raise ValueError("Failed to create transaction: {}".format(str(e))) from e

    @classmethod
    async def get_by_user(cls, db, user_id: UUID) -> list['TokenTransaction']:
        """Get all transactions for a user"""
        stmt = select(cls).where(cls.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def update_status(
        cls,
        db,
        transaction_id: UUID,
        status: TransactionStatus,
        tx_hash: Optional[str] = None
    ) -> 'TokenTransaction':
        """Update transaction status with validation"""
        stmt = select(cls).where(cls.id == transaction_id)
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()
        
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
