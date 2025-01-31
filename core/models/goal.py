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
try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

logger = logging.getLogger(__name__)

from backend.core.models.base import Base
from backend.core.exceptions import (
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
from backend.core.config import settings
from backend.core.models.market import MarketCategory

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
    async def create(cls, db: AsyncSession, redis: aioredis.Redis, user_id: UUID, **kwargs) -> 'Goal':
        """Create a new goal with token validation and proper error handling"""
        try:
            # Validate token balance
            token_balance = await redis.get(f"user:{user_id}:token_balance")
            if not token_balance or float(token_balance) < settings.TOKEN_GOAL_CREATION_COST:
                raise InsufficientBalanceError(
                    f"Insufficient tokens. Required: {settings.TOKEN_GOAL_CREATION_COST}"
                )

            # Validate goal constraints
            if 'constraints' in kwargs:
                GoalBase.validate_constraints(kwargs)

            # Create goal in database
            goal = cls(user_id=user_id, **kwargs)
            db.add(goal)
            await db.commit()
            await db.refresh(goal)

            # Deduct tokens atomically
            async with redis.pipeline() as pipe:
                pipe.decrby(
                    f"user:{user_id}:token_balance",
                    settings.TOKEN_GOAL_CREATION_COST
                )
                pipe.set(
                    f"goal:{goal.id}",
                    goal.to_json(),
                    ex=settings.GOAL_CACHE_TTL
                )
                await pipe.execute()

            # Log creation
            logger.info(
                "Created new goal",
                extra={
                    'goal_id': str(goal.id),
                    'user_id': str(user_id),
                    'token_cost': settings.TOKEN_GOAL_CREATION_COST
                }
            )

            # Queue background task for initial deal search
            try:
                from backend.core.tasks.deal_search import search_deals_for_goal
                await search_deals_for_goal.delay(str(goal.id))
            except ImportError:
                logger.warning(
                    "Deal search task not available",
                    extra={'goal_id': str(goal.id)}
                )

            return goal
            
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create goal",
                extra={
                    'error': str(e),
                    'user_id': str(user_id),
                    'stack_info': True
                }
            )
            raise GoalCreationError(f"Failed to create goal: {str(e)}") from e

    @classmethod
    async def get_by_user(cls, db: AsyncSession, redis_client: aioredis.Redis, user_id: UUID) -> List['Goal']:
        """Get all goals for a user with caching"""
        try:
            # Try to get from cache first
            cached_goals = await redis_client.get(f"user:{user_id}:goals")
            if cached_goals:
                goals_data = json.loads(cached_goals)
                return [cls(**goal_data) for goal_data in goals_data]

            # If not in cache, get from database
            query = select(cls).where(cls.user_id == user_id)
            result = await db.execute(query)
            goals = result.scalars().all()

            # Cache the results
            if goals:
                await redis_client.set(
                    f"user:{user_id}:goals",
                    json.dumps([json.loads(goal.to_json()) for goal in goals]),
                    ex=settings.GOALS_CACHE_TTL
                )

            return goals
        except Exception as e:
            logger.error(
                "Failed to get goals for user",
                extra={
                    'error': str(e),
                    'user_id': str(user_id)
                }
            )
            raise ServiceError(f"Failed to get goals: {str(e)}") from e

    @classmethod
    async def get_by_id(cls, db: AsyncSession, redis_client: aioredis.Redis, goal_id: UUID) -> Optional['Goal']:
        """Get a goal by ID with caching."""
        try:
            # Try to get from cache first
            cached_goal = await redis_client.get(f"goal:{goal_id}")
            if cached_goal:
                goal_data = json.loads(cached_goal)
                return cls(**goal_data)

            # If not in cache, get from database
            query = select(cls).where(cls.id == goal_id)
            result = await db.execute(query)
            goal = result.scalar_one_or_none()

            # Cache the result if found
            if goal:
                await redis_client.set(
                    f"goal:{goal_id}",
                    goal.to_json(),
                    ex=settings.GOAL_CACHE_TTL
                )

            return goal
        except Exception as e:
            logger.error(
                "Failed to get goal by ID",
                extra={
                    'error': str(e),
                    'goal_id': str(goal_id)
                }
            )
            raise ServiceError(f"Failed to get goal: {str(e)}") from e

    async def update(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        update_data: Dict[str, Any]
    ) -> 'Goal':
        """Update goal with new data."""
        try:
            # Validate update data
            update_model = GoalUpdate(**update_data)
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

            self.updated_at = datetime.utcnow()
            
            # Save to database
            await db.commit()
            await db.refresh(self)

            # Update cache
            await redis_client.set(
                f"goal:{self.id}",
                self.to_json(),
                ex=settings.GOAL_CACHE_TTL
            )

            # Invalidate user goals cache
            await redis_client.delete(f"user:{self.user_id}:goals")

            logger.info(
                "Updated goal",
                extra={
                    'goal_id': str(self.id),
                    'updated_fields': list(update_data.keys())
                }
            )

            return self
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to update goal",
                extra={
                    'error': str(e),
                    'goal_id': str(self.id)
                }
            )
            raise GoalUpdateError(f"Failed to update goal: {str(e)}") from e

    async def change_status(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        new_status: GoalStatus,
        reason: Optional[str] = None
    ) -> 'Goal':
        """Change goal status with proper validation and logging."""
        try:
            old_status = self.status
            self.status = new_status
            self.updated_at = datetime.utcnow()
            
            if new_status == GoalStatus.COMPLETED:
                self.processing_stats['completion_time'] = datetime.utcnow().isoformat()
            elif new_status == GoalStatus.ERROR:
                self.processing_stats['last_error'] = {
                    'time': datetime.utcnow().isoformat(),
                    'reason': reason
                }

            # Save to database
            await db.commit()
            await db.refresh(self)

            # Update cache
            await redis_client.set(
                f"goal:{self.id}",
                self.to_json(),
                ex=settings.GOAL_CACHE_TTL
            )

            # Invalidate user goals cache
            await redis_client.delete(f"user:{self.user_id}:goals")

            logger.info(
                "Changed goal status",
                extra={
                    'goal_id': str(self.id),
                    'old_status': old_status.value,
                    'new_status': new_status.value,
                    'reason': reason
                }
            )

            return self
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to change goal status",
                extra={
                    'error': str(e),
                    'goal_id': str(self.id),
                    'new_status': new_status.value
                }
            )
            raise GoalStatusError(f"Failed to change goal status: {str(e)}") from e

    async def process_deal_match(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        deal_id: UUID,
        match_score: float,
        match_details: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Process a new deal match for this goal."""
        try:
            # Update match statistics
            self.matches_found += 1
            self.deals_processed += 1
            
            # Update score metrics
            if self.best_match_score is None or match_score > self.best_match_score:
                self.best_match_score = match_score
            
            # Calculate new average score
            current_avg = self.average_match_score or 0
            self.average_match_score = (
                (current_avg * (self.matches_found - 1) + match_score) / self.matches_found
            )

            # Check if we should notify based on threshold
            should_notify = False
            notification_message = None
            if self.notification_threshold is not None and match_score >= self.notification_threshold:
                should_notify = True
                notification_message = (
                    f"New deal match with score {match_score:.2f} "
                    f"(threshold: {self.notification_threshold:.2f})"
                )

            # Update processing stats
            self.processing_stats['last_match'] = {
                'time': datetime.utcnow().isoformat(),
                'deal_id': str(deal_id),
                'score': match_score,
                'details': match_details
            }

            # Calculate success rate
            total_processed = self.deals_processed or 1
            self.success_rate = self.matches_found / total_processed

            # Save to database
            await db.commit()
            await db.refresh(self)

            # Update cache
            await redis_client.set(
                f"goal:{self.id}",
                self.to_json(),
                ex=settings.GOAL_CACHE_TTL
            )

            logger.info(
                "Processed deal match",
                extra={
                    'goal_id': str(self.id),
                    'deal_id': str(deal_id),
                    'match_score': match_score,
                    'should_notify': should_notify
                }
            )

            return should_notify, notification_message

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to process deal match",
                extra={
                    'error': str(e),
                    'goal_id': str(self.id),
                    'deal_id': str(deal_id)
                }
            )
            raise DealMatchError(f"Failed to process deal match: {str(e)}") from e

    async def check_completion(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis
    ) -> bool:
        """Check if goal should be marked as completed."""
        try:
            should_complete = False
            
            # Check max matches limit
            if self.max_matches and self.matches_found >= self.max_matches:
                should_complete = True
                reason = f"Reached maximum matches ({self.max_matches})"
            
            # Check deadline
            elif self.deadline and datetime.utcnow() >= self.deadline:
                should_complete = True
                reason = "Reached deadline"
            
            # Check token limit
            elif self.max_tokens and self.tokens_spent >= self.max_tokens:
                should_complete = True
                reason = f"Reached maximum token usage ({self.max_tokens})"

            if should_complete:
                await self.change_status(
                    db,
                    redis_client,
                    GoalStatus.COMPLETED,
                    reason=reason
                )

            return should_complete

        except Exception as e:
            logger.error(
                "Failed to check goal completion",
                extra={
                    'error': str(e),
                    'goal_id': str(self.id)
                }
            )
            return False
