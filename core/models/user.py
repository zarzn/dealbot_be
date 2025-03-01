"""User model module.

This module defines the User model and related Pydantic schemas for the AI Agentic Deals System.
It includes validation logic for wallet addresses and referral codes, as well as database operations.

Classes:
    UserBase: Base Pydantic model for user data
    UserCreate: Model for user creation
    UserUpdate: Model for user updates
    UserInDB: Model for database representation
    User: SQLAlchemy model for database table
    UserPreferences: Model for user preferences
"""

from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, field_validator, conint, ConfigDict
from sqlalchemy import (
    Column, String, Boolean, DateTime, Numeric, text, Text, Integer,
    Index, CheckConstraint, UniqueConstraint, Enum as SQLEnum,
    ForeignKey, select, Float, and_, case
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref, column_property
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
try:
    from base58 import b58decode
except ImportError:
    raise ImportError("Please install base58: pip install base58")
import json
import logging
from enum import Enum
import sqlalchemy as sa
from decimal import Decimal, ROUND_DOWN
import random
import string

from core.models.base import Base
from core.exceptions import (
    UserError,
    TokenError,
    WalletError,
    ValidationError,
    InsufficientBalanceError,
    SmartContractError,
    DatabaseError
)
from core.config import settings
from core.models.token_transaction import TokenTransaction
from core.models.token_balance_history import TokenBalanceHistory
from core.models.token_wallet import TokenWallet
from core.models.token_balance import TokenBalance
from core.utils.auth import create_token
from core.models.enums import UserStatus, TokenType, TokenStatus, TokenScope, TokenTransactionType, BalanceChangeType

logger = logging.getLogger(__name__)

class NotificationPreference(str, Enum):
    """User notification preference types."""
    ALL = "all"
    IMPORTANT = "important"
    MINIMAL = "minimal"
    NONE = "none"

class UserBase(BaseModel):
    """Base user model with common fields"""
    email: EmailStr = Field(..., description="User's email address")
    sol_address: Optional[str] = Field(
        None,
        min_length=32,
        max_length=44,
        description="Solana wallet address"
    )
    referral_code: Optional[str] = Field(
        None,
        min_length=6,
        max_length=10,
        pattern=r'^[A-Z0-9]{6,10}$',
        description="User referral code"
    )
    referred_by: Optional[UUID] = None
    preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "theme": "light",
            "notifications": "all",
            "email_notifications": True,
            "push_notifications": False,
            "telegram_notifications": False,
            "discord_notifications": False,
            "deal_alert_threshold": 0.8,
            "auto_buy_enabled": False,
            "auto_buy_threshold": 0.95,
            "max_auto_buy_amount": 100.0,
            "language": "en",
            "timezone": "UTC"
        }
    )
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    notification_channels: List[str] = Field(
        default=["in_app", "email"],
        description="Enabled notification channels"
    )
    name: Optional[str] = Field(None, description="User's name")
    email_verified: bool = Field(False, description="Whether the user's email is verified")
    social_provider: Optional[str] = Field(None, description="User's social provider")
    social_id: Optional[str] = Field(None, description="User's social ID")

    @field_validator('sol_address')
    @classmethod
    def validate_solana_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate Solana wallet address format"""
        if v is None:
            return v
            
        try:
            if len(v) < 32 or len(v) > 44:
                raise WalletError("Invalid Solana address length")
            # Verify base58 encoding
            b58decode(v)
            return v
        except Exception as e:
            logger.error("Invalid Solana address format", extra={'error': str(e)})
            raise WalletError("Invalid Solana address format")

    @field_validator('referral_code')
    @classmethod
    def validate_referral_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate referral code format"""
        if v is None:
            return v
            
        if not v.isalnum():
            raise ValidationError("Referral code must be alphanumeric")
        if not v.isupper():
            raise ValidationError("Referral code must be uppercase")
        return v

    @field_validator('preferences')
    @classmethod
    def validate_preferences(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user preferences"""
        required_fields = {
            "theme": ["light", "dark"],
            "notifications": [p.value for p in NotificationPreference],
            "deal_alert_threshold": (0.0, 1.0),
            "auto_buy_threshold": (0.0, 1.0),
            "max_auto_buy_amount": (0.0, float('inf'))
        }
        
        for field, valid_values in required_fields.items():
            if field not in v:
                v[field] = cls.__fields__['preferences'].default_factory()[field]
            elif isinstance(valid_values, tuple):
                min_val, max_val = valid_values
                if not min_val <= float(v[field]) <= max_val:
                    raise ValidationError(f"{field} must be between {min_val} and {max_val}")
            elif v[field] not in valid_values:
                raise ValidationError(f"Invalid {field}: {v[field]}")
                
        return v

class UserCreate(UserBase):
    """Model for user creation"""
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        pattern=r'[A-Za-z\d@$!%*#?&]{8,}',
        description="User password (must be at least 8 characters long and contain letters, numbers, and special characters)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "StrongPass123!",
                "sol_address": "GsbwXfJraMomNxBcpR3DBNxnKvswrbXcBtXvXrHZCzpe",
                "referral_code": "ABC123"
            }
        }

class UserUpdate(BaseModel):
    """Model for user updates"""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=128,
        pattern=r'[A-Za-z\d@$!%*#?&]{8,}'
    )
    sol_address: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    notification_channels: Optional[List[str]] = None
    status: Optional[UserStatus] = None
    name: Optional[str] = None
    email_verified: Optional[bool] = None
    social_provider: Optional[str] = None
    social_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "sol_address": "GsbwXfJraMomNxBcpR3DBNxnKvswrbXcBtXvXrHZCzpe",
                "preferences": {
                    "theme": "dark",
                    "notifications": "important",
                    "deal_alert_threshold": 0.85
                }
            }
        }

class UserResponse(UserBase):
    """Model for user response"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_payment_at: Optional[datetime]
    active_goals_count: int = Field(default=0)
    total_deals_found: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    total_tokens_spent: Decimal = Field(default=Decimal('0.0'))
    total_rewards_earned: Decimal = Field(default=Decimal('0.0'))

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            UserStatus: lambda v: v.value,
            NotificationPreference: lambda v: v.value,
            Decimal: lambda v: str(v)  # Convert Decimal to string for JSON
        }
    )

class UserInDB(UserBase):
    """Model for user in database with password."""
    password: str
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_payment_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class User(Base):
    """User model."""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(Text, nullable=False)
    sol_address: Mapped[Optional[str]] = mapped_column(String(44), unique=True)
    referral_code: Mapped[Optional[str]] = mapped_column(String(10), unique=True)
    referred_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(SQLEnum(UserStatus, name="userstatus", values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=UserStatus.ACTIVE.value)
    notification_channels: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    social_provider: Mapped[Optional[str]] = mapped_column(String(50))
    social_id: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    active_goals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_deals_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    total_tokens_spent: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    total_rewards_earned: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)

    # Add token_balance as a computed column property
    token_balance = column_property(
        select(func.coalesce(TokenBalance.balance, Decimal('0')))
        .where(TokenBalance.user_id == id)
        .correlate_except(TokenBalance)
        .scalar_subquery()
        .cast(Numeric(18, 8))  # Cast to NUMERIC(18,8) to maintain precision
    )

    # Relationships
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    token_transactions = relationship("TokenTransaction", back_populates="user", cascade="all, delete-orphan")
    token_balance_history = relationship("TokenBalanceHistory", back_populates="user", cascade="all, delete-orphan")
    token_balances = relationship("TokenBalance", back_populates="user", cascade="all, delete-orphan", viewonly=True)  # Add viewonly=True to prevent conflicts
    token_wallets = relationship("TokenWallet", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    tracked_deals = relationship("TrackedDeal", back_populates="user", cascade="all, delete-orphan")
    user_preferences = relationship("UserPreferences", back_populates="user", cascade="all, delete-orphan")
    price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")
    price_predictions = relationship("PricePrediction", back_populates="user", cascade="all, delete-orphan")
    
    # Add relationships from relationships.py to fix conflicts
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan", overlaps="user_preferences")
    token_wallet = relationship("TokenWallet", back_populates="user", uselist=False, cascade="all, delete-orphan", overlaps="token_wallets")

    @property
    def is_active(self) -> bool:
        """Check if user is active."""
        return self.status == UserStatus.ACTIVE.value

    @classmethod
    async def get_by_email(cls, db: AsyncSession, email: str) -> Optional["User"]:
        """Get user by email."""
        stmt = select(cls).where(cls.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_id(cls, db: AsyncSession, user_id: UUID) -> Optional["User"]:
        """Get user by ID."""
        stmt = select(cls).where(cls.id == user_id)
        result = await db.execute(stmt)
        return await result.unique().scalar_one_or_none()

    @classmethod
    async def get_by_social_id(cls, db: AsyncSession, provider: str, social_id: str) -> Optional["User"]:
        """Get user by social provider and ID."""
        stmt = select(cls).where(
            and_(
                cls.social_provider == provider,
                cls.social_id == social_id
            )
        )
        result = await db.execute(stmt)
        return await result.unique().scalar_one_or_none()

    @classmethod
    async def create(cls, db: AsyncSession, **kwargs) -> "User":
        """Create a new user."""
        user = cls(**kwargs)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def update(self, db: AsyncSession, **kwargs) -> "User":
        """Update user attributes."""
        for key, value in kwargs.items():
            setattr(self, key, value)
        await db.flush()
        await db.refresh(self)
        return self

    async def update_token_balance(self, db: AsyncSession, amount: Decimal, reason: str) -> None:
        """Update user's token balance and create history record."""
        from core.models.token_balance import TokenBalance
        from core.models.token_balance_history import TokenBalanceHistory
        from core.models.enums import BalanceChangeType

        # Get current balance
        balance_before = self.token_balance
        balance_after = balance_before + amount

        # Determine change type
        if amount > 0:
            change_type = BalanceChangeType.REWARD.value
        else:
            change_type = BalanceChangeType.DEDUCTION.value
            amount = abs(amount)  # Use absolute value for deductions

        # Create or update token balance
        stmt = select(TokenBalance).where(TokenBalance.user_id == self.id)
        result = await db.execute(stmt)
        token_balance = result.scalar_one_or_none()

        if not token_balance:
            token_balance = TokenBalance(
                user_id=self.id,
                balance=balance_after
            )
            db.add(token_balance)
        else:
            token_balance.balance = balance_after

        await db.flush()

        # Create balance history record
        history = TokenBalanceHistory(
            user_id=self.id,
            token_balance_id=token_balance.id,
            balance_before=balance_before,
            balance_after=balance_after,
            change_amount=amount,
            change_type=change_type,
            reason=reason
        )
        db.add(history)
        await db.flush()

    async def connect_wallet(self, db: AsyncSession, address: str) -> None:
        """Connect a wallet to the user."""
        if self.sol_address:
            raise WalletError("User already has a connected wallet")
            
        self.sol_address = address
        await db.flush()

    async def generate_referral_code(self, db: AsyncSession) -> str:
        """Generate a unique referral code."""
        if self.referral_code:
            return self.referral_code
            
        # Generate a random code and ensure it's unique
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            stmt = select(User).where(User.referral_code == code)
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                self.referral_code = code
                await db.flush()
                return code

    def generate_token(self) -> str:
        """Generate a JWT token for this user."""
        return create_token(str(self.id))

    async def get_token_balance(self, db: AsyncSession) -> Decimal:
        """Get user's token balance.
        
        Args:
            db: Database session
            
        Returns:
            Current token balance with proper precision
        """
        stmt = select(TokenBalance).where(TokenBalance.user_id == self.id)
        result = await db.execute(stmt)
        token_balance = result.scalar_one_or_none()
        
        if not token_balance:
            return Decimal('0').quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
            
        # Ensure proper precision
        return Decimal(str(token_balance.balance)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

    @property
    def token_balance(self) -> Decimal:
        """Get cached token balance or default to 0."""
        if not hasattr(self, '_token_balance'):
            self._token_balance = Decimal('0').quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
        return self._token_balance

    @token_balance.setter
    def token_balance(self, value: Decimal):
        """Set token balance."""
        self._token_balance = Decimal(str(value)).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)

class UserPreferences(BaseModel):
    """Model for user preferences"""
    theme: str = Field(default="light", pattern="^(light|dark)$")
    notifications: NotificationPreference = Field(default=NotificationPreference.ALL)
    email_notifications: bool = Field(default=True)
    push_notifications: bool = Field(default=False)
    telegram_notifications: bool = Field(default=False)
    discord_notifications: bool = Field(default=False)
    deal_alert_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    auto_buy_enabled: bool = Field(default=False)
    auto_buy_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    max_auto_buy_amount: float = Field(default=100.0, ge=0.0)
    language: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")
    timezone: str = Field(default="UTC")

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "dark",
                "notifications": "important",
                "email_notifications": True,
                "deal_alert_threshold": 0.85,
                "auto_buy_enabled": False,
                "auto_buy_threshold": 0.95,
                "max_auto_buy_amount": 100.0,
                "language": "en",
                "timezone": "UTC"
            }
        }


