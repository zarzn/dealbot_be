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
    ForeignKey, select, Float, and_
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
try:
    from base58 import b58decode
except ImportError:
    raise ImportError("Please install base58: pip install base58")
import json
import logging
from enum import Enum
import sqlalchemy as sa
from decimal import Decimal

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
from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet, TokenBalance

logger = logging.getLogger(__name__)

class UserStatus(str, Enum):
    """User status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"

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
    token_balance: Decimal = Field(Decimal('0.0'), ge=Decimal('0.0'), description="User's token balance")
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
    """SQLAlchemy model for user table"""
    __tablename__ = 'users'
    __table_args__ = (
        Index('ix_users_email_status', 'email', 'status'),
        Index('ix_users_wallet', 'sol_address'),
        Index('ix_users_referral', 'referral_code'),
        CheckConstraint('token_balance >= 0', name='ch_positive_balance'),
        UniqueConstraint('email', name='uq_user_email'),
        UniqueConstraint('sol_address', name='uq_user_wallet'),
        UniqueConstraint('referral_code', name='uq_user_referral'),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text('gen_random_uuid()')
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    sol_address: Mapped[Optional[str]] = mapped_column(String(44), unique=True, nullable=True)
    referral_code: Mapped[Optional[str]] = mapped_column(String(10), unique=True, nullable=True)
    referred_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    token_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        default=Decimal('0.0'),
        nullable=False,
        server_default=text('0')
    )
    preferences: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default={
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
        },
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        sa.Enum('active', 'inactive', 'suspended', 'deleted', name='userstatus'),
        nullable=False,
        default='active',
        server_default='active'
    )
    notification_channels: Mapped[List[str]] = mapped_column(JSONB, nullable=False, server_default=text('["in_app", "email"]'))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    social_provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    social_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active_goals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_deals_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    total_tokens_spent: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        default=Decimal('0.0'),
        server_default=text('0')
    )
    total_rewards_earned: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        default=Decimal('0.0'),
        server_default=text('0')
    )

    # Relationships
    goals: Mapped[List["Goal"]] = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    deals: Mapped[List["Deal"]] = relationship(
        "Deal",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    tracked_deals: Mapped[List["TrackedDeal"]] = relationship(
        "TrackedDeal",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    notification_preferences: Mapped["UserPreferences"] = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    chat_messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    token_transactions: Mapped[List["TokenTransaction"]] = relationship(
        "TokenTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    token_balance_history: Mapped[List["TokenBalanceHistory"]] = relationship(
        "TokenBalanceHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    token_wallets: Mapped[List["TokenWallet"]] = relationship(
        "TokenWallet",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    token_balance_record: Mapped["TokenBalance"] = relationship(
        "TokenBalance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    referrals: Mapped[List["User"]] = relationship(
        "User",
        backref=backref("referred_by_user", remote_side=[id]),
        lazy="selectin"
    )
    price_trackers: Mapped[List["PriceTracker"]] = relationship(
        "PriceTracker",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    price_predictions: Mapped[List["PricePrediction"]] = relationship(
        "PricePrediction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    auth_tokens: Mapped[List["AuthToken"]] = relationship(
        "AuthToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User {self.email}>"

    def to_json(self) -> str:
        """Convert user to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'email': self.email,
            'name': self.name,
            'sol_address': self.sol_address,
            'referral_code': self.referral_code,
            'referred_by': str(self.referred_by) if self.referred_by else None,
            'token_balance': float(self.token_balance),
            'status': self.status,
            'preferences': self.preferences,
            'notification_channels': self.notification_channels,
            'email_verified': self.email_verified,
            'social_provider': self.social_provider,
            'social_id': self.social_id,
            'last_payment_at': self.last_payment_at.isoformat() if self.last_payment_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'active_goals_count': self.active_goals_count,
            'total_deals_found': self.total_deals_found,
            'success_rate': float(self.success_rate),
            'total_tokens_spent': float(self.total_tokens_spent),
            'total_rewards_earned': float(self.total_rewards_earned)
        })

    @classmethod
    async def get_by_email(cls, db, email: str) -> Optional['User']:
        """Get user by email"""
        try:
            stmt = select(cls).where(
                and_(
                    cls.email == email,
                    cls.status.cast(String) == UserStatus.ACTIVE.value
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user by email: {str(e)}")
            raise

    @classmethod
    async def get_by_social_id(cls, db, provider: str, social_id: str) -> Optional['User']:
        """Get user by social ID"""
        try:
            stmt = select(cls).where(
                and_(cls.social_provider == provider, cls.social_id == social_id)
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user by social ID: {str(e)}")
            raise

    @classmethod
    async def create(cls, db, **kwargs) -> 'User':
        """Create a new user."""
        try:
            # Generate referral code if not provided
            if 'referral_code' not in kwargs:
                kwargs['referral_code'] = await cls.generate_referral_code(db)
            
            # Ensure token_balance is a Decimal
            if 'token_balance' in kwargs:
                kwargs['token_balance'] = Decimal(str(kwargs['token_balance']))
            else:
                kwargs['token_balance'] = Decimal('0.0')
                
            # Create the user first
            user = cls(**{k: v for k, v in kwargs.items() if k != 'message'})
            db.add(user)
            await db.flush()  # This assigns the ID to the user
            
            # Create initial token balance record
            token_balance = TokenBalance(
                user_id=user.id,
                balance=user.token_balance
            )
            db.add(token_balance)
            
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user: {user.email}")
            return user
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise DatabaseError(
                message=f"Failed to create user: {str(e)}",
                operation="create"
            )

    @classmethod
    async def get_by_wallet(cls, db, wallet_address: str) -> Optional['User']:
        """Get user by wallet address"""
        try:
            if not wallet_address:
                raise WalletError("Wallet address is required")
                
            stmt = select(cls).where(
                cls.sol_address == wallet_address,
                cls.status == 'active'
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user by wallet: {str(e)}")
            raise

    @classmethod
    async def update_token_balance(
        cls,
        db,
        user_id: UUID,
        amount: float,
        operation: str = 'deduction'
    ) -> 'User':
        """Update user token balance with improved error handling"""
        if operation not in ['deduction', 'reward', 'refund']:
            raise ValidationError("Invalid operation type")
        
        try:
            stmt = select(cls).where(
                cls.id == user_id,
                cls.status == 'active'
            ).with_for_update()
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise UserError("User not found or inactive")
                
            if operation == 'deduction':
                if user.token_balance < amount:
                    raise InsufficientBalanceError(
                        required=amount,
                        available=user.token_balance,
                        message=f"Insufficient token balance. Required: {amount}, Available: {user.token_balance}"
                    )
                user.token_balance -= amount
                user.total_tokens_spent += amount
            else:
                user.token_balance += amount
                if operation == 'reward':
                    user.total_rewards_earned += amount
                
            user.last_payment_at = datetime.utcnow()
            
            # Create balance history record
            history = {
                "user_id": user_id,
                "balance_before": user.token_balance + amount if operation == 'deduction' else user.token_balance - amount,
                "balance_after": user.token_balance,
                "change_amount": amount,
                "change_type": operation,
                "reason": f"Token {operation}"
            }
            db.add(TokenBalanceHistory(**history))
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(
                f"Updated token balance for user {user_id}",
                extra={
                    'operation': operation,
                    'amount': amount,
                    'new_balance': user.token_balance
                }
            )
            return user
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to update token balance",
                extra={
                    'user_id': user_id,
                    'operation': operation,
                    'amount': amount,
                    'error': str(e)
                }
            )
            if isinstance(e, (UserError, InsufficientBalanceError, ValidationError)):
                raise
            raise TokenError(f"Failed to update token balance: {str(e)}")

    @classmethod
    async def connect_wallet(
        cls,
        db,
        user_id: UUID,
        wallet_address: str
    ) -> 'User':
        """Connect wallet to user account with improved validation"""
        try:
            # Validate Solana address format
            if not wallet_address or len(wallet_address) < 32 or len(wallet_address) > 44:
                raise WalletError("Invalid Solana address format")
            
            # Verify base58 encoding
            try:
                b58decode(wallet_address)
            except Exception:
                raise WalletError("Invalid Solana address encoding")
                
            user = await db.query(cls).filter(
                cls.id == user_id,
                cls.status == 'active'
            ).with_for_update().first()
            
            if not user:
                raise UserError("User not found or inactive")
                
            # Check if wallet is already connected to another user
            existing_wallet = await db.query(cls).filter(
                cls.sol_address == wallet_address,
                cls.id != user_id,
                cls.status == 'active'
            ).first()
            
            if existing_wallet:
                raise WalletError("Wallet already connected to another user")
                
            # Update user's wallet address
            user.sol_address = wallet_address
            user.updated_at = datetime.utcnow()
            
            # Create wallet record
            wallet = {
                "user_id": user_id,
                "address": wallet_address,
                "is_active": True,
                "network": "mainnet-beta"
            }
            db.add(TokenWallet(**wallet))
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(
                f"Connected wallet for user {user_id}",
                extra={
                    'wallet_address': wallet_address,
                    'user_email': user.email
                }
            )
            return user
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to connect wallet",
                extra={
                    'user_id': user_id,
                    'wallet_address': wallet_address,
                    'error': str(e)
                }
            )
            if isinstance(e, (UserError, WalletError)):
                raise
            raise SmartContractError("connect_wallet", str(e))

    @staticmethod
    async def generate_referral_code(db) -> str:
        """Generate a unique referral code."""
        import random
        import string
        
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check if code exists using SQLAlchemy 2.0 style
            stmt = select(User).where(User.referral_code == code)
            result = await db.execute(stmt)
            exists = result.scalar_one_or_none()
            if not exists:
                return code

    @property
    def is_active(self) -> bool:
        """Check if user is active."""
        return self.status == 'active'

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
