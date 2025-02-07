"""Token model module.

This module defines the token-related models for the AI Agentic Deals System,
including balances and wallets.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from enum import Enum
from sqlalchemy import (
    Column, String, Float, DateTime, Enum as SQLEnum, 
    ForeignKey, JSON, BigInteger, Boolean, Numeric, text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression

from core.models.base import Base, metadata
from .token_transaction import TokenTransaction, TransactionType, TransactionStatus
from .token_balance_history import TokenBalanceHistory
from .token_balance import TokenBalance

class TokenPrice(Base):
    """Token price model"""
    __tablename__ = "token_prices"
    __table_args__ = {'extend_existing': True}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self):
        return f"<TokenPrice {self.price} at {self.timestamp}>"

class TokenWallet(Base):
    """Token wallet model"""
    __tablename__ = "token_wallets"
    __table_args__ = {'extend_existing': True}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address: Mapped[str] = mapped_column(String(44), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=expression.true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    network: Mapped[str] = mapped_column(String(20), nullable=False, default="mainnet-beta", server_default=expression.text("'mainnet-beta'"))
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_wallets")

    def __repr__(self):
        return f"<TokenWallet {self.address}>"

# Pydantic models for API
class TokenPriceResponse(BaseModel):
    """Schema for token price response"""
    id: UUID
    price: float
    timestamp: datetime
    source: Optional[str]
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class TokenBalanceResponse(BaseModel):
    """Schema for token balance response"""
    id: UUID
    user_id: UUID
    balance: float
    last_updated: datetime
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True 