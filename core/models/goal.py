"""Goal model module.

This module defines the Goal model and related Pydantic schemas for the AI Agentic Deals System.
It includes validation logic for goal constraints and database operations.

Classes:
    GoalBase: Base Pydantic model for goal data
    GoalCreate: Model for goal creation
    GoalUpdate: Model for goal updates
    GoalResponse: Model for API responses
    GoalAnalytics: Model for goal analytics data
    Goal: SQLAlchemy model for database table
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, cast, Tuple
from uuid import UUID, uuid4
import enum
import json
import logging
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator, conint, confloat
from sqlalchemy import (
    Column, String, Integer, DateTime, select, update, func, Numeric, text,
    Index, CheckConstraint, UniqueConstraint, Enum as SQLEnum, ForeignKey, Float, Boolean, event, TIMESTAMP, JSON,
    Connection, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column, Mapper
import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

from core.models.base import Base
from core.exceptions import (
    GoalConstraintError,
    GoalValidationError, 
    GoalNotFoundError,
    GoalStatusError,
    ServiceError,
    InsufficientBalanceError,
    InvalidGoalConstraintsError,
    GoalCreationError,
    GoalUpdateError,
    DealMatchError
)
from core.config import settings
from core.models.market import MarketCategory
from core.models.enums import GoalStatus, GoalPriority
from core.models.user import User  # Add missing import for User
from core.exceptions.user_exceptions import UserNotFoundError  # Add missing import for UserNotFoundError

class GoalType(str, enum.Enum):
    """Goal type categories."""
    PRICE_DROP = "price_drop"
    AVAILABILITY = "availability"
    DEAL_MATCH = "deal_match"
    FLASH_SALE = "flash_sale"
    PRICE_PREDICTION = "price_prediction"
    MARKET_ANALYSIS = "market_analysis"
    CUSTOM = "custom"

class GoalBase(BaseModel):
    """Base model for Goal with validation"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)
    priority: Optional[int] = Field(None)
    due_date: Optional[datetime] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # For backward compatibility
    item_category: Optional[str] = Field(None)
    constraints: Optional[Dict[str, Any]] = Field(None)
    deadline: Optional[datetime] = Field(None)
    max_matches: Optional[int] = Field(None, gt=0)
    max_tokens: Optional[float] = Field(None)
    notification_threshold: Optional[float] = Field(None)
    auto_buy_threshold: Optional[float] = Field(None)

    @model_validator(mode='after')
    def validate_constraints(self) -> 'GoalBase':
        """Validate goal constraints structure if provided"""
        # Skip validation if constraints not provided
        if not self.constraints:
            return self
            
        constraints = self.constraints
        
        # For backward compatibility, convert some fields to float if they're strings
        if self.max_tokens and isinstance(self.max_tokens, str):
            try:
                self.max_tokens = float(self.max_tokens)
            except ValueError:
                raise GoalConstraintError("max_tokens must be a number")
                
        if self.notification_threshold and isinstance(self.notification_threshold, str):
            try:
                self.notification_threshold = float(self.notification_threshold)
            except ValueError:
                raise GoalConstraintError("notification_threshold must be a number")
                
        if self.auto_buy_threshold and isinstance(self.auto_buy_threshold, str):
            try:
                self.auto_buy_threshold = float(self.auto_buy_threshold)
            except ValueError:
                raise GoalConstraintError("auto_buy_threshold must be a number")
        
        # Check for camelCase versions of price fields and normalize them
        if 'maxPrice' in constraints and 'max_price' not in constraints:
            constraints['max_price'] = constraints['maxPrice']
        if 'minPrice' in constraints and 'min_price' not in constraints:
            constraints['min_price'] = constraints['minPrice']
                
        # Only validate certain fields if they exist
        if 'max_price' in constraints and 'min_price' in constraints:
            try:
                max_price = float(constraints['max_price'])
                min_price = float(constraints['min_price'])
                
                if max_price <= min_price:
                    raise GoalConstraintError("max_price must be greater than min_price")
                if min_price < 0:
                    raise GoalConstraintError("min_price cannot be negative")
                if max_price > settings.MAX_GOAL_PRICE:
                    raise GoalConstraintError(f"max_price cannot exceed {settings.MAX_GOAL_PRICE}")
            except (ValueError, TypeError):
                raise GoalConstraintError("Price constraints must be valid numbers")
            
        # Handle price_range if provided instead of min/max price
        if 'price_range' in constraints:
            price_range = constraints['price_range']
            if not isinstance(price_range, dict):
                raise GoalConstraintError("price_range must be a dictionary")
                
            if 'min' in price_range and 'max' in price_range:
                try:
                    max_price = float(price_range['max'])
                    min_price = float(price_range['min'])
                    
                    if max_price <= min_price:
                        raise GoalConstraintError("price_range.max must be greater than price_range.min")
                    if min_price < 0:
                        raise GoalConstraintError("price_range.min cannot be negative")
                    if max_price > settings.MAX_GOAL_PRICE:
                        raise GoalConstraintError(f"price_range.max cannot exceed {settings.MAX_GOAL_PRICE}")
                except (ValueError, TypeError):
                    raise GoalConstraintError("Price range must contain valid numbers")
            
        # Validate array fields if they exist
        array_fields = ['keywords', 'categories', 'brands', 'conditions']
        for field in array_fields:
            if field in constraints:
                if not isinstance(constraints[field], list):
                    raise GoalConstraintError(f"{field} must be a list")
                if len(constraints[field]) > 100:
                    raise GoalConstraintError(f"{field} list cannot exceed 100 items")
                
        return self

    @field_validator('deadline')
    @classmethod
    def validate_deadline(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate deadline is in the future and within limits."""
        if v is not None:
            now = datetime.now(timezone.utc)
            if not v.tzinfo:
                raise ValueError("Deadline must be timezone-aware")
                
            # Check if this is a validation for a new record or an existing one
            data = info.data
            is_existing_record = data.get('id') is not None
            
            # Only validate that deadline is in the future for new records
            if not is_existing_record and v <= now:
                raise GoalValidationError("Deadline must be in the future")
                
            # Still validate max deadline for all records
            max_deadline = now + timedelta(days=settings.MAX_GOAL_DEADLINE_DAYS)
            if not is_existing_record and v > max_deadline:
                raise GoalValidationError("Deadline cannot exceed {} days".format(settings.MAX_GOAL_DEADLINE_DAYS))
        return v

class GoalCreate(GoalBase):
    """Model for creating a new goal"""
    user_id: Optional[UUID] = None
    initial_search: bool = Field(default=True)

class GoalUpdate(BaseModel):
    """Model for updating a goal"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[GoalStatus] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # For backward compatibility
    item_category: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    deadline: Optional[datetime] = None
    max_matches: Optional[int] = Field(None, gt=0)
    max_tokens: Optional[str] = Field(None)
    notification_threshold: Optional[str] = Field(None)
    auto_buy_threshold: Optional[str] = Field(None)

    @model_validator(mode='after')
    def validate_constraints(self) -> 'GoalUpdate':
        """Validate goal constraints structure"""
        constraints = getattr(self, 'constraints', None)
        if constraints is None:
            return self
            
        # Ensure constraints is a dictionary
        if not isinstance(constraints, dict):
            raise InvalidGoalConstraintsError("Constraints must be a dictionary")
            
        # Only validate if we have constraints
        if constraints:  
            required_fields = ['max_price', 'min_price', 'brands', 'conditions', 'keywords']
            
            # Check for missing fields and try to find camelCase equivalents
            missing_fields = []
            for field in required_fields:
                if field not in constraints:
                    # Try to find camelCase version (e.g., convert min_price to minPrice)
                    camel_field = ''.join([field.split('_')[0]] + [word.capitalize() for word in field.split('_')[1:]])
                    if camel_field in constraints:
                        # Found camelCase version, copy the value to snake_case
                        constraints[field] = constraints[camel_field]
                    else:
                        missing_fields.append(field)
            
            if missing_fields:
                raise InvalidGoalConstraintsError(
                    f"Constraints missing required fields: {', '.join(missing_fields)}"
                )
            
            # Validate price constraints
            if 'max_price' in constraints and 'min_price' in constraints:
                try:
                    # Check both camelCase and snake_case versions
                    max_price = float(constraints.get('max_price', constraints.get('maxPrice', 0)))
                    min_price = float(constraints.get('min_price', constraints.get('minPrice', 0)))
                    
                    # Ensure the snake_case versions exist in the constraints
                    constraints['max_price'] = max_price
                    constraints['min_price'] = min_price
                    
                    if max_price <= min_price:
                        raise InvalidGoalConstraintsError("max_price must be greater than min_price")
                    if min_price < 0:
                        raise InvalidGoalConstraintsError("min_price cannot be negative")
                except (ValueError, TypeError):
                    raise InvalidGoalConstraintsError("Price values must be valid numbers")
                
        return self

class GoalResponse(GoalBase):
    """Response model for Goal"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    last_checked_at: Optional[datetime] = None
    matches_found: int = Field(default=0)
    deals_processed: int = Field(default=0)
    tokens_spent: float = Field(default=0.0)
    rewards_earned: float = Field(default=0.0)
    last_processed_at: Optional[datetime] = None
    processing_stats: Dict[str, Any] = Field(default_factory=dict)
    best_match_score: Optional[float] = None
    average_match_score: Optional[float] = None
    active_deals_count: int = Field(default=0)
    success_rate: float = Field(default=0.0)

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            GoalStatus: lambda v: v.value,
            GoalPriority: lambda v: v.value,
            MarketCategory: lambda v: v.value
        }
    
    @model_validator(mode='before')
    @classmethod
    def convert_priority_and_metadata(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert priority string to enum and ensure metadata is a dict."""
        if isinstance(data, dict):
            # Handle priority conversion
            if 'priority' in data:
                priority = data['priority']
                
                # Handle string priority values
                if isinstance(priority, str):
                    # Map priority strings to numbers
                    priority_str_map = {
                        "critical": 5,
                        "urgent": 4,
                        "high": 3,
                        "medium": 2,
                        "low": 1
                    }
                    data['priority'] = priority_str_map.get(priority.lower(), 3)
                # Make sure priority is an int if it's still not
                if not isinstance(data['priority'], int):
                    try:
                        data['priority'] = int(data['priority'])
                    except (ValueError, TypeError):
                        # Default to medium priority (3) if conversion fails
                        data['priority'] = 3
            
            # Ensure metadata is a dict
            if 'metadata' in data:
                if data['metadata'] is None:
                    data['metadata'] = {}
                elif hasattr(data['metadata'], '__dict__'):
                    # Convert object to dict if it has __dict__ attribute
                    data['metadata'] = vars(data['metadata'])
                elif hasattr(data['metadata'], 'to_dict'):
                    # If the object has a to_dict method, use it
                    data['metadata'] = data['metadata'].to_dict()
                elif not isinstance(data['metadata'], dict):
                    # If it's neither dict nor has __dict__, create empty dict
                    data['metadata'] = {}
        # Handle SQLAlchemy model objects
        elif hasattr(data, '__dict__') and hasattr(data, 'priority') and hasattr(data, 'metadata'):
            # Create a new dictionary with the model's attributes
            model_dict = {}
            for key, value in vars(data).items():
                if not key.startswith('_'):
                    model_dict[key] = value
            
            # Apply the same conversions to the model_dict
            return cls.convert_priority_and_metadata(model_dict)
        
        return data
        
    @model_validator(mode='after')
    def handle_expired_deadline(self) -> 'GoalResponse':
        """Mark goals with past deadlines as expired in metadata"""
        if self.deadline and self.deadline.tzinfo:
            now = datetime.now(timezone.utc)
            if self.deadline <= now:
                # Initialize metadata if it doesn't exist
                if not hasattr(self, 'metadata') or self.metadata is None:
                    self.metadata = {}
                
                # Add expired flag to metadata
                self.metadata['expired'] = True
                self.metadata['expired_at'] = self.deadline.isoformat()
                
                # Update status to expired if the current status is active
                if self.status == GoalStatus.ACTIVE:
                    self.status = GoalStatus.EXPIRED
        return self

class GoalAnalytics(BaseModel):
    """Model for goal analytics data"""
    goal_id: UUID
    user_id: UUID
    matches_found: int = Field(default=0)
    deals_processed: int = Field(default=0)
    tokens_spent: float = Field(default=0.0)
    rewards_earned: float = Field(default=0.0)
    success_rate: float = Field(default=0.0)
    best_match_score: Optional[float] = None
    average_match_score: Optional[float] = None
    active_deals_count: int = Field(default=0)
    price_trends: Dict[str, Any] = Field(default_factory=dict)
    market_analysis: Dict[str, Any] = Field(default_factory=dict)
    deal_history: List[Dict[str, Any]] = Field(default_factory=list)
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    start_date: datetime
    end_date: datetime
    period: str
    
    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class GoalTemplateCreate(BaseModel):
    """Model for creating a goal template"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: MarketCategory
    constraints: Dict[str, Any] = Field(...)
    is_public: bool = Field(default=False)
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @model_validator(mode='after')
    def validate_constraints(self) -> 'GoalTemplateCreate':
        """Validate template constraints structure"""
        constraints = self.constraints
        required_fields = ['max_price', 'min_price', 'brands', 'conditions', 'keywords']
        
        # Check for missing fields and try to find camelCase equivalents
        missing_fields = []
        for field in required_fields:
            if field not in constraints:
                # Try to find camelCase version (e.g., convert min_price to minPrice)
                camel_field = ''.join([field.split('_')[0]] + [word.capitalize() for word in field.split('_')[1:]])
                if camel_field in constraints:
                    # Found camelCase version, copy the value to snake_case
                    constraints[field] = constraints[camel_field]
                else:
                    missing_fields.append(field)
        
        if missing_fields:
            raise GoalConstraintError(
                f"Missing required constraint fields: {', '.join(missing_fields)}"
            )
        
        # Validate price constraints
        try:
            # Try both camelCase and snake_case versions, prioritizing snake_case
            max_price = float(constraints.get('max_price', constraints.get('maxPrice', 0)))
            min_price = float(constraints.get('min_price', constraints.get('minPrice', 0)))
            
            # Ensure the snake_case versions exist in the constraints
            constraints['max_price'] = max_price
            constraints['min_price'] = min_price
            
            if max_price <= min_price:
                raise GoalConstraintError("max_price must be greater than min_price")
            if min_price < 0:
                raise GoalConstraintError("min_price cannot be negative")
            if max_price > settings.MAX_GOAL_PRICE:
                raise GoalConstraintError(f"max_price cannot exceed {settings.MAX_GOAL_PRICE}")
        except (ValueError, TypeError) as e:
            raise GoalConstraintError("Price constraints must be valid numbers") from e
            
        return self

class GoalTemplate(GoalTemplateCreate):
    """Model for goal template"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    usage_count: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    average_savings: float = Field(default=0.0)
    is_featured: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    
    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            MarketCategory: lambda v: v.value
        }

class GoalSharePermission(str, enum.Enum):
    """Goal sharing permission levels."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class GoalShare(BaseModel):
    """Model for sharing a goal with other users"""
    share_with: List[UUID] = Field(..., min_items=1)
    permissions: GoalSharePermission = Field(default=GoalSharePermission.READ)
    message: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None
    notify_users: bool = Field(default=True)

    @field_validator('expires_at')
    @classmethod
    def validate_expiry(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate expiry date is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiry date must be in the future")
        return v

class GoalShareResponse(BaseModel):
    """Response model for goal sharing"""
    goal_id: UUID
    shared_by: UUID
    shared_with: List[UUID]
    permissions: GoalSharePermission
    shared_at: datetime
    expires_at: Optional[datetime]
    status: str = Field(default="active")
    message: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            GoalSharePermission: lambda v: v.value
        }

class Goal(Base):
    """Goal database model."""
    __tablename__ = "goals"
    __table_args__ = (
        UniqueConstraint('user_id', 'title', name='uq_user_goal_title'),
        CheckConstraint('max_tokens >= 0', name='ch_positive_max_tokens'),
        Index('ix_goals_user_status', 'user_id', 'status'),
        Index('ix_goals_deadline', 'deadline'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    item_category: Mapped[MarketCategory] = mapped_column(SQLEnum(MarketCategory, values_callable=lambda x: [e.value for e in x]), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    constraints: Mapped[Dict] = mapped_column(JSONB, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[GoalStatus] = mapped_column(SQLEnum(GoalStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=GoalStatus.ACTIVE)
    priority: Mapped[GoalPriority] = mapped_column(SQLEnum(GoalPriority, values_callable=lambda x: [e.value for e in x]), nullable=False, default=GoalPriority.MEDIUM)
    max_matches: Mapped[Optional[int]] = mapped_column(Integer)
    max_tokens: Mapped[Optional[float]] = mapped_column(Float)
    notification_threshold: Mapped[Optional[float]] = mapped_column(Float)
    auto_buy_threshold: Mapped[Optional[float]] = mapped_column(Float)
    matches_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_spent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rewards_earned: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    processing_stats: Mapped[Optional[Dict]] = mapped_column(JSONB)
    best_match_score: Mapped[Optional[float]] = mapped_column(Float)
    average_match_score: Mapped[Optional[float]] = mapped_column(Float)
    active_deals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("User", back_populates="goals")
    deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="goal", cascade="all, delete-orphan")
    matched_deals = relationship("DealMatch", back_populates="goal", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="goal", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize a Goal instance with validation."""
        # Set timestamps first
        now = datetime.now(timezone.utc)
        kwargs.setdefault('created_at', now)
        kwargs.setdefault('updated_at', now)
        
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        """String representation of the goal."""
        return f"<Goal {self.id}: {self.title} ({self.status})>"

    def to_json(self) -> Dict[str, Any]:
        """Convert goal to JSON representation."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "item_category": self.item_category,
            "title": self.title,
            "description": self.description,
            "constraints": self.constraints,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "priority": self.priority.value,
            "max_matches": self.max_matches,
            "max_tokens": float(self.max_tokens) if self.max_tokens else None,
            "notification_threshold": float(self.notification_threshold) if self.notification_threshold else None,
            "auto_buy_threshold": float(self.auto_buy_threshold) if self.auto_buy_threshold else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "matches_found": self.matches_found,
            "deals_processed": self.deals_processed,
            "tokens_spent": float(self.tokens_spent),
            "rewards_earned": float(self.rewards_earned),
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "processing_stats": self.processing_stats,
            "best_match_score": float(self.best_match_score) if self.best_match_score else None,
            "average_match_score": float(self.average_match_score) if self.average_match_score else None,
            "active_deals_count": self.active_deals_count
        }

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        redis: Redis,
        goal_data: GoalCreate
    ) -> 'Goal':
        """Create a new goal."""
        try:
            # Verify token balance
            required_balance = settings.GOAL_CREATION_COST
            cached_balance = await redis.get(f"balance:{goal_data.user_id}")
            
            if cached_balance is not None:
                current_balance = Decimal(cached_balance.decode())
            else:
                # Get user balance from database
                user_result = await db.execute(
                    select(User).where(User.id == goal_data.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    raise UserNotFoundError("User not found")
                current_balance = user.token_balance
                
                # Cache the balance
                await redis.setex(
                    f"balance:{goal_data.user_id}",
                    300,  # 5 minutes TTL
                    str(current_balance)
                )
            
            if current_balance < required_balance:
                raise InsufficientBalanceError(
                    reason=f"Insufficient balance for goal creation. Required: {required_balance}, Current: {current_balance}",
                    available=current_balance,
                    required=required_balance
                )
            
            # Create goal
            goal = cls(**goal_data.model_dump(exclude={'initial_search'}))
            db.add(goal)
            await db.commit()
            await db.refresh(goal)
            
            # Cache goal data
            await redis.setex(
                f"goal:{goal.id}",
                3600,  # 1 hour TTL
                json.dumps(goal.to_dict())
            )
            
            # Add to user's goals list
            await redis.lpush(f"user_goals:{goal_data.user_id}", str(goal.id))
            await redis.expire(f"user_goals:{goal_data.user_id}", 3600)  # 1 hour TTL
            
            return goal
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating goal: {e}")
            raise GoalCreationError(f"Could not create goal: {str(e)}")

    @classmethod
    async def get_by_id(
        cls,
        goal_id: UUID,
        db: AsyncSession,
        redis: Redis
    ) -> Optional['Goal']:
        """Get a goal by its ID."""
        try:
            # Try to get from cache first
            cached_goal = await redis.get(f"goal:{goal_id}")
            if cached_goal:
                goal_data = json.loads(cached_goal.decode())
                return cls(**goal_data)
            
            # If not in cache, get from database
            result = await db.execute(
                select(cls).where(cls.id == goal_id)
            )
            goal = result.scalar_one_or_none()
            
            if goal:
                # Cache the goal
                await redis.setex(
                    f"goal:{goal_id}",
                    3600,  # 1 hour TTL
                    json.dumps(goal.to_dict())
                )
            
            return goal
        except Exception as e:
            logger.error(f"Error getting goal by ID: {e}")
            raise GoalNotFoundError(f"Could not retrieve goal: {str(e)}")

    @classmethod
    async def get_by_user(
        cls,
        user_id: UUID,
        db: AsyncSession,
        redis: Redis,
        status: Optional[GoalStatus] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List['Goal']:
        """Get goals for a user."""
        try:
            query = select(cls).where(cls.user_id == user_id)
            
            if status:
                query = query.where(cls.status == status)
            
            query = query.order_by(cls.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await db.execute(query)
            goals = result.scalars().all()
            
            # Cache the goals
            for goal in goals:
                await redis.setex(
                    f"goal:{goal.id}",
                    3600,  # 1 hour TTL
                    json.dumps(goal.to_dict())
                )
            
            return goals
        except Exception as e:
            logger.error(f"Error getting goals for user: {e}")
            raise ServiceError(
                service="goal",
                operation="get_by_user",
                message=f"Could not retrieve goals: {str(e)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert goal to dictionary for caching."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "item_category": self.item_category,
            "title": self.title,
            "description": self.description,
            "constraints": self.constraints,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "priority": self.priority,
            "max_matches": self.max_matches,
            "max_tokens": float(self.max_tokens) if self.max_tokens else None,
            "notification_threshold": float(self.notification_threshold) if self.notification_threshold else None,
            "auto_buy_threshold": float(self.auto_buy_threshold) if self.auto_buy_threshold else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "matches_found": self.matches_found,
            "deals_processed": self.deals_processed,
            "tokens_spent": float(self.tokens_spent) if self.tokens_spent else 0.0,
            "rewards_earned": float(self.rewards_earned) if self.rewards_earned else 0.0,
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "processing_stats": self.processing_stats,
            "best_match_score": float(self.best_match_score) if self.best_match_score else None,
            "average_match_score": float(self.average_match_score) if self.average_match_score else None
        }

    async def check_completion(self, session) -> None:
        """Check if the goal should be marked as completed or expired."""
        old_status = self.status
        if self.deadline and self.deadline <= datetime.now(timezone.utc):
            self.status = GoalStatus.EXPIRED.value
        elif self.max_matches and self.matches_found >= self.max_matches:
            self.status = GoalStatus.COMPLETED.value
        
        # Update timestamp if status changed
        if old_status != self.status:
            self.updated_at = datetime.now(timezone.utc)
            await session.flush()

@event.listens_for(Goal, "before_insert")
@event.listens_for(Goal, "before_update")
def validate_goal(mapper: Mapper, connection: Connection, target: Goal) -> None:
    """Validate goal before insert/update."""
    # Validate constraints format
    if isinstance(target.constraints, str):
        try:
            # Try to convert string constraints to dict
            import json
            target.constraints = json.loads(target.constraints)
        except:
            # If conversion fails, use a default valid constraints format
            target.constraints = {
                'min_price': 100.0,
                'max_price': 500.0,
                'brands': ['samsung', 'apple', 'sony'],
                'conditions': ['new', 'like_new', 'good'],
                'keywords': ['electronics', 'gadget', 'tech']
            }
    
    # Ensure constraints is a dictionary
    if not isinstance(target.constraints, dict):
        # Use default constraints if not a valid dict
        target.constraints = {
            'min_price': 100.0,
            'max_price': 500.0,
            'brands': ['samsung', 'apple', 'sony'],
            'conditions': ['new', 'like_new', 'good'],
            'keywords': ['electronics', 'gadget', 'tech']
        }

    # Add default title if missing
    if target.title is None:
        target.title = f"Goal for {target.item_category.value if isinstance(target.item_category, MarketCategory) else 'item'}"

    # Validate item category
    if target.item_category is None:
        # If item_category is None, provide a default
        target.item_category = MarketCategory.ELECTRONICS
    elif isinstance(target.item_category, str):
        try:
            # Try to convert string to enum
            valid_categories = [cat.value.lower() for cat in MarketCategory]
            if target.item_category.lower() in valid_categories:
                # Convert to enum using the properly cased value
                for cat in MarketCategory:
                    if cat.value.lower() == target.item_category.lower():
                        target.item_category = cat
                        break
            else:
                # If not a recognized value, set to default
                target.item_category = MarketCategory.ELECTRONICS
        except (ValueError, AttributeError):
            # If any error in conversion, set to default
            target.item_category = MarketCategory.ELECTRONICS
    elif not isinstance(target.item_category, MarketCategory):
        # If not a string or MarketCategory, set to default
        target.item_category = MarketCategory.ELECTRONICS

    # Validate priority
    if target.priority is not None:
        try:
            if isinstance(target.priority, str):
                # Try to find the enum member that matches this string value
                for priority in GoalPriority:
                    if priority.value.lower() == target.priority.lower():
                        target.priority = priority.value
                        break
                else:
                    # No matching enum value found, use default
                    target.priority = GoalPriority.MEDIUM.value
            elif isinstance(target.priority, int):
                # Convert int 1-5 to enum values
                if target.priority == 5:
                    target.priority = GoalPriority.CRITICAL.value
                elif target.priority == 4:
                    target.priority = GoalPriority.URGENT.value
                elif target.priority == 3:
                    target.priority = GoalPriority.HIGH.value
                elif target.priority == 2:
                    target.priority = GoalPriority.MEDIUM.value
                elif target.priority == 1:
                    target.priority = GoalPriority.LOW.value
                else:
                    # For invalid integer values, use default
                    target.priority = GoalPriority.MEDIUM.value
            elif isinstance(target.priority, GoalPriority):
                # If it's already a GoalPriority enum, just extract the value
                target.priority = target.priority.value
            else:
                # For any other type, set to default
                target.priority = GoalPriority.MEDIUM.value
        except ValueError:
            # If conversion fails, set to default
            target.priority = GoalPriority.MEDIUM.value

    # Validate max matches and max tokens
    if target.max_matches is not None and target.max_matches <= 0:
        raise GoalValidationError("Max matches must be positive")
    if target.max_tokens is not None and target.max_tokens <= 0:
        raise GoalValidationError("Max tokens must be positive")

    # Validate thresholds
    if target.notification_threshold is not None:
        if not 0 <= target.notification_threshold <= 1:
            raise GoalValidationError("Thresholds must be between 0 and 1")
    if target.auto_buy_threshold is not None:
        if not 0 <= target.auto_buy_threshold <= 1:
            raise GoalValidationError("Thresholds must be between 0 and 1")

    # Validate deadline
    if target.deadline is not None:
        if not isinstance(target.deadline, type(datetime.now())):
            raise GoalValidationError("Deadline must be a datetime object")
        if target.deadline.tzinfo is None:
            raise GoalValidationError("Deadline must be timezone-aware")
        # For new goals, ensure deadline is in the future
        if not target.id and target.deadline <= datetime.now(timezone.utc):
            raise GoalValidationError("Deadline must be in the future")

    # Validate required fields in constraints
    required_fields = {'min_price', 'max_price', 'keywords', 'brands', 'conditions'}
    missing_fields = required_fields - set(target.constraints.keys())
    if missing_fields:
        # Check if missing fields might be present in camelCase format
        camel_to_snake = {
            'min_price': 'minPrice',
            'max_price': 'maxPrice'
        }
        
        # Copy to avoid modifying during iteration
        fixed_missing_fields = list(missing_fields)
        for field in list(missing_fields):
            camel_field = camel_to_snake.get(field)
            if camel_field and camel_field in target.constraints:
                # Found camelCase version, add the snake_case version
                target.constraints[field] = target.constraints[camel_field]
                fixed_missing_fields.remove(field)
        
        # Check if we still have missing fields after normalization
        if fixed_missing_fields:
            raise GoalConstraintError(f"Missing required constraint fields: {', '.join(fixed_missing_fields)}")
    
    # Validate price constraints - check both snake_case and camelCase versions
    min_price_key = 'min_price' if 'min_price' in target.constraints else 'minPrice'
    max_price_key = 'max_price' if 'max_price' in target.constraints else 'maxPrice'
    
    # Validate min_price
    if min_price_key in target.constraints:
        min_price = target.constraints[min_price_key]
        if not isinstance(min_price, (int, float)) or min_price < 0:
            raise GoalConstraintError("Minimum price must be a non-negative number")
        # Always store as snake_case for consistency
        if min_price_key == 'minPrice':
            target.constraints['min_price'] = min_price
    
    # Validate max_price
    if max_price_key in target.constraints:
        max_price = target.constraints[max_price_key]
        if not isinstance(max_price, (int, float)) or max_price <= 0:
            raise GoalConstraintError("Maximum price must be a positive number")
        # Always store as snake_case for consistency
        if max_price_key == 'maxPrice':
            target.constraints['max_price'] = max_price
    
    # Check min_price < max_price
    if 'min_price' in target.constraints and 'max_price' in target.constraints:
        if target.constraints['min_price'] >= target.constraints['max_price']:
            raise GoalConstraintError("Min price must be less than max price")

    # Validate list fields
    list_fields = ['keywords', 'brands', 'conditions']
    for field in list_fields:
        if not isinstance(target.constraints[field], list):
            raise GoalConstraintError(f"{field} must be a list")
        
        # Add default keywords if empty
        if field == 'keywords' and not target.constraints[field]:
            target.constraints['keywords'] = ['product', 'deal']
        # Only check for empty lists for keywords and conditions, allow brands to be empty
        elif field != 'brands' and not target.constraints[field]:
            raise GoalConstraintError(f"{field} list cannot be empty")
            
        if not all(isinstance(item, str) for item in target.constraints[field]):
            raise GoalConstraintError(f"All {field} must be strings")

