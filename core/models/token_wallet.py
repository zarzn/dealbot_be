"""Token wallet model module.

This module defines the TokenWallet model and related Pydantic schemas for managing
user token wallets in the AI Agentic Deals System.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, String, Boolean, DateTime, text, ForeignKey, Numeric, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import expression
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict

from core.models.base import Base
from core.models.enums import TransactionType, TransactionStatus

class TokenWallet(Base):
    """SQLAlchemy model for user token wallets."""
    __tablename__ = "token_wallets"
    __table_args__ = (
        Index('ix_token_wallets_user_address', 'user_id', 'address'),
        {'extend_existing': True}
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text('true'))
    network = Column(String(50), nullable=False, server_default="mainnet-beta")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    last_used = Column(DateTime(timezone=True), nullable=True)
    data = Column(MutableDict.as_mutable(JSONB), nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_wallets")
    transactions = relationship("WalletTransaction", back_populates="wallet", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TokenWallet {self.address} ({self.network})>"

class WalletTransaction(Base):
    """SQLAlchemy model for wallet operations."""
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        Index('ix_wallet_transactions_wallet_type', 'wallet_id', 'type'),
        Index('ix_wallet_transactions_user_status', 'user_id', 'status'),
        Index('ix_wallet_transactions_created_at', 'created_at'),
        {'extend_existing': True}
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    wallet_id = Column(PG_UUID(as_uuid=True), ForeignKey("token_wallets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(SQLEnum(TransactionType, values_callable=lambda x: [e.value.lower() for e in x]), nullable=False)
    amount = Column(Numeric(18, 8), nullable=False)
    status = Column(SQLEnum(TransactionStatus, values_callable=lambda x: [e.value.lower() for e in x]), nullable=False, default=TransactionStatus.PENDING.value)
    tx_hash = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    transaction_metadata = Column(JSONB, nullable=True)

    # Relationships
    wallet = relationship("TokenWallet", back_populates="transactions", lazy="joined")
    user = relationship("User", back_populates="wallet_transactions", lazy="joined")

    def __repr__(self):
        return f"<WalletTransaction {self.type} {self.amount} ({self.status})>"

class TokenWalletCreate(BaseModel):
    """Schema for creating a wallet"""
    address: str
    network: str = "mainnet-beta"
    data: Optional[Dict[str, Any]] = None

class TokenWalletUpdate(BaseModel):
    """Schema for updating a wallet"""
    is_active: Optional[bool] = None
    data: Optional[Dict[str, Any]] = None

class TokenWalletResponse(BaseModel):
    """Schema for wallet response"""
    id: UUID
    user_id: UUID
    address: str
    is_active: bool
    network: str
    created_at: datetime
    last_used: Optional[datetime]
    data: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)

class WalletConnectRequest(BaseModel):
    """Schema for wallet connection request."""
    address: str
    network: str = "mainnet-beta"
    signature: Optional[str] = None
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate wallet address format."""
        if not v or len(v) != 44:
            raise ValueError("Invalid Solana wallet address format")
        return v

    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network type."""
        valid_networks = {'mainnet-beta', 'testnet', 'devnet'}
        if v not in valid_networks:
            raise ValueError(f"Invalid network. Must be one of: {', '.join(valid_networks)}")
        return v 