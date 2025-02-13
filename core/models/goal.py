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

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, cast, Tuple
from uuid import UUID, uuid4
import enum
import json
import logging
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator, conint, confloat
from sqlalchemy import (
    Column, String, Integer, DateTime, select, update, func, Numeric, text,
    Index, CheckConstraint, UniqueConstraint, Enum as SQLEnum, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, Mapped, mapped_column
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

class GoalStatus(str, enum.Enum):
    """Goal status types."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ERROR = "error"

class GoalPriority(int, enum.Enum):
    """Goal priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class GoalBase(BaseModel):
    """Base model for Goal with validation"""
    item_category: MarketCategory = Field(...)
    title: str = Field(..., min_length=1, max_length=255)
    constraints: Dict[str, Any] = Field(...)
    deadline: Optional[datetime] = Field(None)
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)
    priority: GoalPriority = Field(default=GoalPriority.MEDIUM)
    max_matches: Optional[int] = Field(None, gt=0)
    max_tokens: Optional[float] = Field(None, gt=0)
    notification_threshold: Optional[float] = Field(None, ge=0, le=1)
    auto_buy_threshold: Optional[float] = Field(None, ge=0, le=1)

    @model_validator(mode='after')
    def validate_constraints(self) -> 'GoalBase':
        """Validate goal constraints structure"""
        constraints = self.constraints
        required_fields = ['max_price', 'min_price', 'brands', 'conditions', 'keywords']
        
        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in constraints]
        if missing_fields:
            raise GoalConstraintError(
                f"Missing required constraint fields: {', '.join(missing_fields)}"
            )
        
        # Validate price constraints
        try:
            max_price = float(constraints['max_price'])
            min_price = float(constraints['min_price'])
            
            if max_price <= min_price:
                raise GoalConstraintError("max_price must be greater than min_price")
            if min_price < 0:
                raise GoalConstraintError("min_price cannot be negative")
            if max_price > settings.MAX_GOAL_PRICE:
                raise GoalConstraintError(f"max_price cannot exceed {settings.MAX_GOAL_PRICE}")
        except (ValueError, TypeError) as e:
            raise GoalConstraintError("Price constraints must be valid numbers") from e
            
        # Validate other constraints
        if not isinstance(constraints['brands'], list):
            raise GoalConstraintError("brands must be a list")
        if not isinstance(constraints['conditions'], list):
            raise GoalConstraintError("conditions must be a list")
        if not isinstance(constraints['keywords'], list):
            raise GoalConstraintError("keywords must be a list")
            
        return self

    @field_validator('deadline')
    def validate_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate deadline is in the future and within limits."""
        if v is not None:
            now = datetime.utcnow()
            if v <= now:
                raise ValueError("Deadline must be in the future")
            max_deadline = now + timedelta(days=settings.MAX_GOAL_DEADLINE_DAYS)
            if v > max_deadline:
                raise ValueError(f"Deadline cannot exceed {settings.MAX_GOAL_DEADLINE_DAYS} days")
        return v

class GoalCreate(GoalBase):
    """Model for creating a new goal"""
    user_id: UUID
    initial_search: bool = Field(default=True)

class GoalUpdate(BaseModel):
    """Model for updating a goal"""
    item_category: Optional[MarketCategory] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    constraints: Optional[Dict[str, Any]] = None
    deadline: Optional[datetime] = None
    status: Optional[GoalStatus] = None
    priority: Optional[GoalPriority] = None
    max_matches: Optional[int] = Field(None, gt=0)
    max_tokens: Optional[float] = Field(None, gt=0)
    notification_threshold: Optional[float] = Field(None, ge=0, le=1)
    auto_buy_threshold: Optional[float] = Field(None, ge=0, le=1)

    @model_validator(mode='after')
    def validate_constraints(self) -> 'GoalUpdate':
        """Validate goal constraints structure"""
        constraints = self.constraints
        if constraints is None:
            return self
            
        required_fields = ['max_price', 'min_price', 'brands', 'conditions', 'keywords']
        if not all(field in constraints for field in required_fields):
            raise InvalidGoalConstraintsError(
                f"Constraints must include: {', '.join(required_fields)}"
            )
        
        # Validate price constraints
        max_price = float(constraints['max_price'])
        min_price = float(constraints['min_price'])
        
        if max_price <= min_price:
            raise InvalidGoalConstraintsError("max_price must be greater than min_price")
        if min_price < 0:
            raise InvalidGoalConstraintsError("min_price cannot be negative")
        if max_price > settings.MAX_GOAL_PRICE:
            raise InvalidGoalConstraintsError(f"max_price cannot exceed {settings.MAX_GOAL_PRICE}")
            
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
        
        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in constraints]
        if missing_fields:
            raise GoalConstraintError(
                f"Missing required constraint fields: {', '.join(missing_fields)}"
            )
        
        # Validate price constraints
        try:
            max_price = float(constraints['max_price'])
            min_price = float(constraints['min_price'])
            
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
    """SQLAlchemy model for Goal"""
    __tablename__ = 'goals'
    __table_args__ = (
        Index('ix_goals_user_status', 'user_id', 'status'),
        Index('ix_goals_priority_deadline', 'priority', 'deadline'),
        CheckConstraint('tokens_spent >= 0', name='ch_positive_tokens'),
        CheckConstraint('rewards_earned >= 0', name='ch_positive_rewards'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    item_category: Mapped[str] = mapped_column(
        SQLEnum(MarketCategory, name='marketcategory', create_constraint=True, native_enum=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    constraints: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        SQLEnum(GoalStatus, name='goalstatus', create_constraint=True, native_enum=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=GoalStatus.ACTIVE.value,
        server_default=GoalStatus.ACTIVE.value
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=GoalPriority.MEDIUM.value,
        server_default=str(GoalPriority.MEDIUM.value)
    )
    max_matches: Mapped[Optional[int]] = mapped_column(Integer)
    max_tokens: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    notification_threshold: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    auto_buy_threshold: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    matches_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_spent: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    rewards_earned: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    last_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    processing_stats: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    best_match_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    average_match_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    active_deals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)

    # Relationships
    user = relationship("User", back_populates="goals")
    deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="goal", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="goal", cascade="all, delete-orphan")

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
            "constraints": self.constraints,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "priority": int(self.priority),
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
            "active_deals_count": self.active_deals_count,
            "success_rate": float(self.success_rate)
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
                    f"Insufficient balance for goal creation. Required: {required_balance}, Current: {current_balance}"
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
            raise ServiceError(f"Could not retrieve goals: {str(e)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert goal to dictionary for caching."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "item_category": self.item_category,
            "title": self.title,
            "constraints": self.constraints,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "priority": self.priority,
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
            "average_match_score": float(self.average_match_score) if self.average_match_score else None
        }
