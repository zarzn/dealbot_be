"""Token model module.

This module defines the token-related models for the AI Agentic Deals System,
including balances and wallets.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from enum import Enum
from sqlalchemy import (
    Column, String, Float, DateTime, Enum as SQLEnum, 
    ForeignKey, JSON, BigInteger, Boolean, Numeric, text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression
from pydantic import field_validator, Field

from core.models.base import Base
from .token_transaction import TokenTransaction, TransactionType, TransactionStatus
from .token_balance_history import TokenBalanceHistory
from .token_balance import TokenBalance

class TokenPrice(Base):
    """Token price model"""
    __tablename__ = "token_prices"
    __table_args__ = {'extend_existing': True}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    price = Column(Numeric(18, 8), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    source = Column(String(50), nullable=True)
    data = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<TokenPrice {self.price} at {self.timestamp}>"

class TokenWallet(Base):
    """Token wallet model"""
    __tablename__ = "token_wallets"
    __table_args__ = {'extend_existing': True}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address = Column(String(44), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    last_used = Column(DateTime(timezone=True), nullable=True)
    network = Column(String(20), nullable=False, default="mainnet-beta", server_default=expression.text("'mainnet-beta'"))
    data = Column(JSONB, nullable=True)

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

class TransactionHistoryResponse(BaseModel):
    """Schema for transaction history response."""
    id: UUID
    user_id: UUID
    type: str
    amount: float
    status: str
    tx_hash: Optional[str] = None
    created_at: datetime
    data: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate transaction type."""
        valid_types = {'payment', 'reward', 'refund', 'deduction'}
        if v not in valid_types:
            raise ValueError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate transaction status."""
        valid_statuses = {'pending', 'completed', 'failed'}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

class TokenPricingResponse(BaseModel):
    """Schema for token pricing response."""
    id: UUID
    service_type: str
    token_cost: float
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = True
    description: Optional[str] = None
    pricing_metadata: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v: str) -> str:
        """Validate service type."""
        valid_services = {
            'send_message', 
            'get_deals', 
            'deal_analytics', 
            'deal_recommendations',
            'create_goal',
            'update_goal',
            'delete_goal',
            'share_goal',
            'create_template',
            'chat_analytics'
        }
        if v not in valid_services:
            raise ValueError(f"Invalid service type. Must be one of: {', '.join(valid_services)}")
        return v
        
    @field_validator('token_cost')
    @classmethod
    def validate_token_cost(cls, v: float) -> float:
        """Validate token cost."""
        if v < 0:
            raise ValueError("Token cost cannot be negative")
        return v

class TokenAnalytics(BaseModel):
    """Schema for token analytics response."""
    total_tokens_spent: float
    total_transactions: int
    transactions_by_type: Dict[str, int]
    transactions_by_status: Dict[str, int]
    average_transaction_amount: float
    most_used_services: List[Dict[str, Any]]
    spending_trends: List[Dict[str, Any]]
    balance_history: List[Dict[str, Any]]
    service_usage_stats: Dict[str, Any]
    wallet_activity: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    period: str = Field(default="7d")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v: str) -> str:
        """Validate analytics period."""
        valid_periods = {'1d', '7d', '30d', '90d', 'all'}
        if v not in valid_periods:
            raise ValueError(f"Invalid period. Must be one of: {', '.join(valid_periods)}")
        return v
        
    @field_validator('total_tokens_spent')
    @classmethod
    def validate_total_tokens(cls, v: float) -> float:
        """Validate total tokens spent."""
        if v < 0:
            raise ValueError("Total tokens spent cannot be negative")
        return v

class TokenReward(BaseModel):
    """Schema for token reward."""
    id: UUID
    user_id: UUID
    amount: float
    reward_type: str
    reason: str
    status: str = Field(default="pending")
    reward_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Validate reward amount."""
        if v <= 0:
            raise ValueError("Reward amount must be positive")
        return v
        
    @field_validator('reward_type')
    @classmethod
    def validate_reward_type(cls, v: str) -> str:
        """Validate reward type."""
        valid_types = {
            'referral',
            'activity_bonus',
            'goal_achievement',
            'deal_discovery',
            'feedback',
            'early_adopter',
            'loyalty',
            'promotion'
        }
        if v not in valid_types:
            raise ValueError(f"Invalid reward type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate reward status."""
        valid_statuses = {'pending', 'processing', 'completed', 'failed', 'cancelled'}
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v

class TokenUsageStats(BaseModel):
    """Schema for token usage statistics."""
    user_id: UUID
    period: str = Field(default="7d")
    total_usage: float
    usage_by_service: Dict[str, float]
    daily_usage: List[Dict[str, Any]]
    peak_usage_time: Optional[datetime] = None
    service_frequency: Dict[str, int]
    cost_efficiency: Dict[str, float]
    usage_patterns: Dict[str, Any]
    rewards_earned: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v: str) -> str:
        """Validate stats period."""
        valid_periods = {'1d', '7d', '30d', '90d', 'all'}
        if v not in valid_periods:
            raise ValueError(f"Invalid period. Must be one of: {', '.join(valid_periods)}")
        return v
        
    @field_validator('total_usage')
    @classmethod
    def validate_total_usage(cls, v: float) -> float:
        """Validate total usage."""
        if v < 0:
            raise ValueError("Total usage cannot be negative")
        return v
        
    @field_validator('rewards_earned')
    @classmethod
    def validate_rewards(cls, v: float) -> float:
        """Validate rewards earned."""
        if v < 0:
            raise ValueError("Rewards earned cannot be negative")
        return v
        
    @field_validator('usage_by_service')
    @classmethod
    def validate_usage_by_service(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate service usage values."""
        valid_services = {
            'send_message', 
            'get_deals', 
            'deal_analytics', 
            'deal_recommendations',
            'create_goal',
            'update_goal',
            'delete_goal',
            'share_goal',
            'create_template',
            'chat_analytics'
        }
        for service, usage in v.items():
            if service not in valid_services:
                raise ValueError(f"Invalid service: {service}")
            if usage < 0:
                raise ValueError(f"Usage for {service} cannot be negative")
        return v

class TokenTransferRequest(BaseModel):
    """Schema for token transfer request."""
    from_user_id: UUID
    to_user_id: Optional[UUID] = None
    to_address: Optional[str] = None
    amount: float
    transfer_type: str = Field(default="internal")
    memo: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    network: str = Field(default="mainnet-beta")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Validate transfer amount."""
        if v <= 0:
            raise ValueError("Transfer amount must be positive")
        return v
        
    @field_validator('transfer_type')
    @classmethod
    def validate_transfer_type(cls, v: str) -> str:
        """Validate transfer type."""
        valid_types = {'internal', 'external', 'withdrawal', 'deposit'}
        if v not in valid_types:
            raise ValueError(f"Invalid transfer type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network type."""
        valid_networks = {'mainnet-beta', 'testnet', 'devnet'}
        if v not in valid_networks:
            raise ValueError(f"Invalid network. Must be one of: {', '.join(valid_networks)}")
        return v
        
    @field_validator('to_address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate wallet address if provided."""
        if v is not None:
            if not v or len(v) != 44:
                raise ValueError("Invalid Solana wallet address format")
        return v
        
    @field_validator('to_user_id', 'to_address')
    @classmethod
    def validate_destination(cls, v: Any, info: Any) -> Any:
        """Validate that either to_user_id or to_address is provided."""
        data = info.data
        if not data.get('to_user_id') and not data.get('to_address'):
            raise ValueError("Either to_user_id or to_address must be provided")
        return v

class TokenBurnRequest(BaseModel):
    """Schema for token burn request."""
    user_id: UUID
    amount: float
    reason: str
    burn_type: str = Field(default="manual")
    memo: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    network: str = Field(default="mainnet-beta")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Validate burn amount."""
        if v <= 0:
            raise ValueError("Burn amount must be positive")
        return v
        
    @field_validator('burn_type')
    @classmethod
    def validate_burn_type(cls, v: str) -> str:
        """Validate burn type."""
        valid_types = {'manual', 'automatic', 'penalty', 'expiration', 'governance'}
        if v not in valid_types:
            raise ValueError(f"Invalid burn type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network type."""
        valid_networks = {'mainnet-beta', 'testnet', 'devnet'}
        if v not in valid_networks:
            raise ValueError(f"Invalid network. Must be one of: {', '.join(valid_networks)}")
        return v
        
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate burn reason."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Burn reason is required")
        if len(v) > 255:
            raise ValueError("Burn reason must be less than 255 characters")
        return v

class TokenMintRequest(BaseModel):
    """Schema for token mint request."""
    to_user_id: Optional[UUID] = None
    to_address: Optional[str] = None
    amount: float
    mint_type: str = Field(default="manual")
    reason: str
    memo: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    network: str = Field(default="mainnet-beta")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Validate mint amount."""
        if v <= 0:
            raise ValueError("Mint amount must be positive")
        return v
        
    @field_validator('mint_type')
    @classmethod
    def validate_mint_type(cls, v: str) -> str:
        """Validate mint type."""
        valid_types = {'manual', 'reward', 'airdrop', 'promotion', 'governance'}
        if v not in valid_types:
            raise ValueError(f"Invalid mint type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network type."""
        valid_networks = {'mainnet-beta', 'testnet', 'devnet'}
        if v not in valid_networks:
            raise ValueError(f"Invalid network. Must be one of: {', '.join(valid_networks)}")
        return v
        
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate mint reason."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Mint reason is required")
        if len(v) > 255:
            raise ValueError("Mint reason must be less than 255 characters")
        return v
        
    @field_validator('to_address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate wallet address if provided."""
        if v is not None:
            if not v or len(v) != 44:
                raise ValueError("Invalid Solana wallet address format")
        return v
        
    @field_validator('to_user_id', 'to_address')
    @classmethod
    def validate_destination(cls, v: Any, info: Any) -> Any:
        """Validate that either to_user_id or to_address is provided."""
        data = info.data
        if not data.get('to_user_id') and not data.get('to_address'):
            raise ValueError("Either to_user_id or to_address must be provided")
        return v

class TokenStakeRequest(BaseModel):
    """Schema for token stake request."""
    user_id: UUID
    amount: float
    stake_period: int = Field(default=30, description="Staking period in days")
    stake_type: str = Field(default="fixed")
    reward_rate: float = Field(default=0.0, description="Annual percentage rate (APR)")
    auto_renew: bool = Field(default=False)
    memo: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None
    network: str = Field(default="mainnet-beta")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Validate stake amount."""
        if v <= 0:
            raise ValueError("Stake amount must be positive")
        return v
        
    @field_validator('stake_period')
    @classmethod
    def validate_stake_period(cls, v: int) -> int:
        """Validate stake period."""
        valid_periods = {7, 14, 30, 60, 90, 180, 365}
        if v not in valid_periods:
            raise ValueError(f"Invalid stake period. Must be one of: {', '.join(map(str, valid_periods))} days")
        return v
        
    @field_validator('stake_type')
    @classmethod
    def validate_stake_type(cls, v: str) -> str:
        """Validate stake type."""
        valid_types = {'fixed', 'flexible', 'governance', 'liquidity'}
        if v not in valid_types:
            raise ValueError(f"Invalid stake type. Must be one of: {', '.join(valid_types)}")
        return v
        
    @field_validator('reward_rate')
    @classmethod
    def validate_reward_rate(cls, v: float) -> float:
        """Validate reward rate."""
        if v < 0:
            raise ValueError("Reward rate cannot be negative")
        if v > 100:
            raise ValueError("Reward rate cannot exceed 100%")
        return v
        
    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network type."""
        valid_networks = {'mainnet-beta', 'testnet', 'devnet'}
        if v not in valid_networks:
            raise ValueError(f"Invalid network. Must be one of: {', '.join(valid_networks)}")
        return v 