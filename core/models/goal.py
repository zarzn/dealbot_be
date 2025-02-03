"""Goal model module.

This module defines the Goal model and related Pydantic schemas for the AI Agentic Deals System.
It includes validation logic for goal constraints and database operations.

Classes:
    GoalBase: Base Pydantic model for goal data
    GoalCreate: Model for goal creation
    GoalUpdate: Model for goal updates
    GoalResponse: Model for API responses
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
    Index, CheckConstraint, UniqueConstraint, Enum as SQLAlchemyEnum
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
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    item_category: Mapped[str] = mapped_column(SQLAlchemyEnum(MarketCategory), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    constraints: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        SQLAlchemyEnum(GoalStatus),
        nullable=False,
        default=GoalStatus.ACTIVE,
        server_default=GoalStatus.ACTIVE.value
    )
    priority: Mapped[int] = mapped_column(
        SQLAlchemyEnum(GoalPriority),
        nullable=False,
        default=GoalPriority.MEDIUM,
        server_default=str(GoalPriority.MEDIUM.value)
    )
    max_matches: Mapped[Optional[int]] = mapped_column(Integer)
    max_tokens: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    notification_threshold: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    auto_buy_threshold: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text('NOW()'),
        onupdate=text('NOW()')
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
    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)

    # Relationships
    deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the goal."""
        return f"<Goal {self.title} ({self.status.value})>"

    def to_json(self) -> str:
        """Convert goal to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'user_id': str(self.user_id),
            'item_category': self.item_category.value if isinstance(self.item_category, MarketCategory) else self.item_category,
            'title': self.title,
            'constraints': self.constraints,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status': self.status.value if isinstance(self.status, GoalStatus) else self.status,
            'priority': int(self.priority.value if isinstance(self.priority, GoalPriority) else self.priority),
            'max_matches': self.max_matches,
            'max_tokens': float(self.max_tokens) if self.max_tokens is not None else None,
            'notification_threshold': float(self.notification_threshold) if self.notification_threshold is not None else None,
            'auto_buy_threshold': float(self.auto_buy_threshold) if self.auto_buy_threshold is not None else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_checked_at': self.last_checked_at.isoformat() if self.last_checked_at else None,
            'matches_found': self.matches_found,
            'deals_processed': self.deals_processed,
            'tokens_spent': float(self.tokens_spent),
            'rewards_earned': float(self.rewards_earned),
            'last_processed_at': self.last_processed_at.isoformat() if self.last_processed_at else None,
            'processing_stats': self.processing_stats,
            'best_match_score': float(self.best_match_score) if self.best_match_score is not None else None,
            'average_match_score': float(self.average_match_score) if self.average_match_score is not None else None,
            'active_deals_count': self.active_deals_count,
            'success_rate': float(self.success_rate)
        })

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
