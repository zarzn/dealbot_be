from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum
from sqlalchemy import (
    Column, String, Float, DateTime, Enum as SQLEnum, 
    ForeignKey, JSON, BigInteger, Boolean
)
from sqlalchemy.orm import relationship

from .base import Base
from .user import User
from .token_pricing import TokenPricing  # Import TokenPricing from its own module

class TransactionType(str, Enum):
    """Transaction types"""
    PAYMENT = "payment"
    REFUND = "refund"
    REWARD = "reward"
    TRANSFER = "transfer"

class TransactionStatus(str, Enum):
    """Transaction status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TokenTransaction(Base):
    """Token transaction model"""
    __tablename__ = "token_transactions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    data = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    signature = Column(String(88), nullable=True)
    slot = Column(BigInteger, nullable=True)
    network = Column(String(20), nullable=False, default="mainnet-beta")
    fee = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_transactions")

    def __repr__(self):
        return f"<TokenTransaction {self.id}: {self.type} {self.amount}>"

class TokenPrice(Base):
    """Token price model"""
    __tablename__ = "token_prices"

    id = Column(String(36), primary_key=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String(50), nullable=True)
    data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<TokenPrice {self.price} at {self.timestamp}>"

class TokenBalance(Base):
    """Token balance model"""
    __tablename__ = "token_balances"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    balance = Column(Float, nullable=False, default=0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_balance")

    def __repr__(self):
        return f"<TokenBalance {self.user_id}: {self.balance}>"

class TokenWallet(Base):
    """Token wallet model"""
    __tablename__ = "token_wallets"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address = Column(String(44), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    network = Column(String(20), nullable=False, default="mainnet-beta")
    data = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="token_wallets")

    def __repr__(self):
        return f"<TokenWallet {self.address}>"

# Pydantic models for API
class TransactionCreate(BaseModel):
    """Schema for creating a transaction"""
    type: TransactionType
    amount: float
    data: Optional[Dict[str, Any]] = None

class TransactionUpdate(BaseModel):
    """Schema for updating a transaction"""
    status: Optional[TransactionStatus] = None
    error: Optional[str] = None
    signature: Optional[str] = None
    slot: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: str
    user_id: str
    type: TransactionType
    amount: float
    status: TransactionStatus
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    signature: Optional[str]
    slot: Optional[int]
    network: str
    fee: Optional[float]

    class Config:
        from_attributes = True

class TokenPriceResponse(BaseModel):
    """Schema for token price response"""
    id: str
    price: float
    timestamp: datetime
    source: Optional[str]
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class TokenBalanceResponse(BaseModel):
    """Schema for token balance response"""
    id: str
    user_id: str
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
    id: str
    user_id: str
    address: str
    is_active: bool
    network: str
    created_at: datetime
    last_used: Optional[datetime]
    data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class WalletConnectRequest(BaseModel):
    wallet_address: str

class TransactionHistoryResponse(BaseModel):
    id: UUID
    type: str
    amount: Decimal
    status: str
    signature: Optional[str] = None
    slot: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TokenPricingResponse(BaseModel):
    service_type: str
    token_cost: Decimal
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = True

    class Config:
        from_attributes = True 