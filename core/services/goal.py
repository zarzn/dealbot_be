from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from pydantic import BaseModel, field_validator
from fastapi import BackgroundTasks
from datetime import datetime, timezone, timedelta
import json
from sqlalchemy.orm import joinedload
from redis.asyncio import Redis

from core.models.goal import (
    GoalCreate, 
    GoalResponse, 
    GoalUpdate,
    GoalAnalytics,
    Goal as GoalModel
)
from core.models.goal_types import GoalStatus, GoalPriority
from core.exceptions import (
    GoalError,
    GoalNotFoundError,
    InvalidGoalDataError,
    GoalConstraintError,
    GoalLimitExceededError,
    APIServiceUnavailableError,
    DatabaseError,
    ValidationError,
    CacheOperationError,
    TokenError,
    NetworkError
)
from core.services.token import TokenService
from core.config import settings
from core.utils.redis import get_redis_client
from core.tasks.goal_status import update_goal_status_task
from core.models.user import User
from core.services.base import BaseService
from core.services.ai import AIService
from core.models.enums import MarketCategory
from core.models.deal_score import DealMatch as DealMatchModel

logger = logging.getLogger(__name__)

class GoalCacheKey(BaseModel):
    user_id: UUID
    goal_id: Union[UUID, str]
    
    @field_validator('goal_id')
    def validate_goal_id(cls, v):
        """Validate that goal_id is either a UUID or the string 'all'"""
        if isinstance(v, str) and v != 'all':
            try:
                return UUID(v)
            except ValueError:
                raise ValueError("goal_id must be a valid UUID or the string 'all'")
        return v

# Add MatchDetails class for analytics
class MatchDetails(BaseModel):
    """Details for matched deals."""
    deal_id: UUID
    user_id: UUID
    match_score: float
    matched_at: datetime

class GoalService(BaseService[GoalModel, GoalCreate, GoalUpdate]):
    """Service layer for goal management operations"""
    
    model = GoalModel
    
    def __init__(self, session: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize goal service.
        
        Args:
            session: Database session
            redis_service: Optional Redis service for caching
        """
        super().__init__(session=session, redis_service=redis_service)
        self.ai_service = AIService()
        self.session = session
        
    async def init_redis(self) -> None:
        """Initialize Redis connection with retry mechanism"""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self._redis = await get_redis_client()
                logger.info("Successfully connected to Redis")
                return
            except Exception as e:
                logger.warning(
                    f"Redis connection attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    
        logger.error("Failed to connect to Redis after multiple attempts")
        raise APIServiceUnavailableError("Failed to establish Redis connection")
            
    async def close_redis(self) -> None:
        """Close Redis connection with error handling"""
        try:
            if self._redis:
                await self._redis.close()
                logger.info("Redis connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
            raise APIServiceUnavailableError("Failed to close Redis connection") from e

    async def create_goal(
        self, 
        user_id: UUID,
        title: str,
        item_category: str,
        constraints: Dict[str, Any],
        deadline: Optional[datetime] = None,
        status: str = GoalStatus.ACTIVE,
        priority: str = GoalPriority.MEDIUM,
        max_matches: Optional[int] = None,
        max_tokens: Optional[float] = None,
        notification_threshold: Optional[float] = None,
        auto_buy_threshold: Optional[float] = None,
        **kwargs
    ) -> GoalResponse:
        """Create a new goal.
        
        Args:
            user_id: User ID
            title: Goal title
            item_category: Category of the item
            constraints: Goal constraints
            deadline: Optional deadline
            status: Goal status
            priority: Goal priority
            max_matches: Maximum number of matches
            max_tokens: Maximum tokens to spend
            notification_threshold: Notification threshold
            auto_buy_threshold: Auto buy threshold
            
        Returns:
            GoalResponse: Created goal details
            
        Raises:
            GoalError: If goal creation fails
        """
        try:
            # Validate the goal data
            await self.validate_goal_data({
                "title": title,
                "item_category": item_category,
                "constraints": constraints,
                "deadline": deadline,
                "status": status,
                "priority": priority,
                "max_matches": max_matches,
                "max_tokens": max_tokens,
                "notification_threshold": notification_threshold,
                "auto_buy_threshold": auto_buy_threshold
            })
            
            # Validate constraints
            await self.validate_constraints(constraints)
            
            # Create goal model
            goal_model = GoalModel(
                user_id=user_id,
                title=title,
                item_category=item_category,
                constraints=constraints,
                deadline=deadline,
                status=status,
                priority=priority,
                max_matches=max_matches,
                max_tokens=max_tokens,
                notification_threshold=notification_threshold,
                auto_buy_threshold=auto_buy_threshold,
                created_at=datetime.utcnow()
            )
            
            # Add to database
            self.session.add(goal_model)
            await self.session.commit()
            await self.session.refresh(goal_model)
            
            # Schedule background tasks using Celery
            try:
                update_goal_status_task.delay(goal_model.id, user_id)
            except Exception as e:
                # Log the error but don't fail the goal creation
                logger.warning(f"Failed to schedule goal status update task: {str(e)}")
            
            # Create response
            response = GoalResponse(
                id=goal_model.id,
                user_id=goal_model.user_id,
                title=goal_model.title,
                item_category=goal_model.item_category,
                constraints=goal_model.constraints,
                deadline=goal_model.deadline,
                status=goal_model.status,
                priority=goal_model.priority,
                max_matches=goal_model.max_matches,
                max_tokens=goal_model.max_tokens,
                notification_threshold=goal_model.notification_threshold,
                auto_buy_threshold=goal_model.auto_buy_threshold,
                created_at=goal_model.created_at,
                updated_at=goal_model.updated_at
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Goal creation failed: {str(e)}")
            raise GoalError(f"Failed to create goal: {str(e)}")

    async def get_goals(self, user_id: UUID) -> List[GoalResponse]:
        """Get all goals for a user with caching"""
        try:
            # Try to get from cache first
            cached_goals = await self._get_cached_goals(user_id)
            if cached_goals:
                logger.debug(
                    f"Retrieved {len(cached_goals)} goals from cache for user {user_id}",
                    extra={"user_id": user_id}
                )
                return cached_goals
                
            # Fallback to database
            query = select(GoalModel).options(
                joinedload(GoalModel.matched_deals)
            ).filter(GoalModel.user_id == user_id)
            result = await self.session.execute(query)
            goals = result.scalars().unique().all()
            
            # Cache the results
            await self._cache_goals(user_id, goals)
            
            logger.debug(
                f"Retrieved {len(goals)} goals from database for user {user_id}",
                extra={"user_id": user_id}
            )
            return [await self._to_response(goal) for goal in goals]
        except Exception as e:
            logger.error(
                f"Failed to get goals for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise GoalNotFoundError(f"Failed to get goals: {str(e)}") from e

    async def get_goal(self, goal_id: UUID, user_id: Optional[UUID] = None) -> GoalResponse:
        """Get a specific goal with caching"""
        try:
            # If user_id is not provided, we need to find the goal first to get its user_id
            if user_id is None:
                # Query just for the goal to get its user_id
                query = select(GoalModel).filter(GoalModel.id == goal_id)
                result = await self.session.execute(query)
                goal_for_user = result.scalar_one_or_none()
                if not goal_for_user:
                    raise GoalNotFoundError(f"Goal {goal_id} not found")
                user_id = goal_for_user.user_id
            
            # Try to get from cache first
            cached_goal = await self._get_cached_goal(user_id, goal_id)
            if cached_goal:
                logger.debug(
                    f"Retrieved goal {goal_id} from cache for user {user_id}",
                    extra={"goal_id": goal_id, "user_id": user_id}
                )
                return cached_goal
                
            # Fallback to database
            query = select(GoalModel).options(
                joinedload(GoalModel.matched_deals)
            ).filter(
                GoalModel.id == goal_id,
                GoalModel.user_id == user_id
            )
            result = await self.session.execute(query)
            # When using joinedload for collections, we need to call unique() first
            result = result.unique()
            goal = result.scalar_one_or_none()
            if not goal:
                raise GoalNotFoundError(f"Goal {goal_id} not found")
                
            # Cache the result
            await self._cache_goal(goal)
            
            logger.debug(
                f"Retrieved goal {goal_id} from database for user {user_id}",
                extra={"goal_id": goal_id, "user_id": user_id}
            )
            return await self._to_response(goal)
        except Exception as e:
            logger.error(
                f"Failed to get goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalNotFoundError(f"Failed to get goal: {str(e)}") from e

    async def update_goal_status(
        self, 
        user_id: UUID,
        goal_id: UUID, 
        status: str
    ) -> GoalResponse:
        """Update goal status with validation and cache invalidation"""
        if status not in GoalStatus.list():
            raise InvalidGoalDataError(
                f"Invalid status. Must be one of: {', '.join(GoalStatus.list())}"
            )
            
        try:
            # Get and validate goal
            goal = await self.get_goal(goal_id)
            
            # Update status
            await self.session.execute(
                update(GoalModel)
                .where(GoalModel.id == goal_id)
                .values(status=status, updated_at=datetime.utcnow())
            )
            await self.session.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(user_id, goal_id)
            
            # Schedule background task using Celery
            try:
                update_goal_status_task.delay(goal_id, user_id)
            except Exception as e:
                # Log the error but don't fail the goal status update
                logger.warning(f"Failed to schedule goal status update task: {str(e)}")
            
            logger.info(
                f"Updated goal {goal_id} status to {status}",
                extra={"goal_id": goal_id, "status": status}
            )
            return goal
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to update goal {goal_id} status: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalError(f"Failed to update goal status: {str(e)}") from e

    async def delete_goal(self, goal_id: UUID, user_id: Optional[UUID] = None) -> None:
        """Delete a goal with cache invalidation
        
        Args:
            goal_id: Goal ID to delete
            user_id: Optional User ID (if not provided, it will be fetched)
            
        Raises:
            GoalNotFoundError: If goal not found
        """
        try:
            # If user_id is not provided, we need to find the goal first to get its user_id
            if user_id is None:
                goal = await self.get_goal(goal_id)
                user_id = goal.user_id
            else:
                # Verify goal exists for this user
                await self.get_goal(goal_id, user_id)
            
            # Delete goal
            await self.session.execute(
                delete(GoalModel)
                .where(GoalModel.id == goal_id)
            )
            await self.session.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(user_id, goal_id)
            
            logger.info(
                f"Deleted goal {goal_id}",
                extra={"goal_id": goal_id}
            )
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to delete goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalNotFoundError(f"Failed to delete goal: {str(e)}") from e
            
    async def _cache_goal(self, goal: GoalModel) -> None:
        """Cache a single goal"""
        try:
            if self._redis:
                cache_key = GoalCacheKey(user_id=goal.user_id, goal_id=goal.id)
                await self._redis.set(
                    cache_key.json(),
                    GoalResponse.from_orm(goal).json(),
                    expire=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(
                f"Failed to cache goal {goal.id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal.id}
            )
            raise APIServiceUnavailableError("Failed to cache goal") from e
            
    async def _cache_goals(self, user_id: UUID, goals: List[GoalModel]) -> None:
        """Cache multiple goals for a user"""
        try:
            if self._redis:
                # Use a string directly for the all goals cache key to avoid UUID validation
                all_goals_key = f"goal_cache:{user_id}:all"
                await self._redis.set(
                    all_goals_key,
                    [GoalResponse.from_orm(goal).json() for goal in goals],
                    expire=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(
                f"Failed to cache goals for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise APIServiceUnavailableError("Failed to cache goals") from e
            
    async def _get_cached_goal(self, user_id: UUID, goal_id: UUID) -> Optional[GoalResponse]:
        """Get a cached goal by ID"""
        try:
            if self._redis:
                cache_key = GoalCacheKey(user_id=user_id, goal_id=goal_id)
                cached_data = await self._redis.get(cache_key.json())
                if cached_data:
                    # Handle both dict and string responses from Redis
                    if isinstance(cached_data, dict):
                        return GoalResponse.model_validate(cached_data)
                    else:
                        return GoalResponse.parse_raw(cached_data)
            return None
        except Exception as e:
            logger.warning(
                f"Failed to get cached goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise APIServiceUnavailableError("Failed to get cached goal") from e
            
    async def _get_cached_goals(self, user_id: UUID) -> Optional[List[GoalResponse]]:
        """Get cached goals for a user"""
        try:
            if self._redis:
                # Use a string directly for the all goals cache key to avoid UUID validation
                all_goals_key = f"goal_cache:{user_id}:all"
                cached_data = await self._redis.get(all_goals_key)
                if cached_data:
                    result = []
                    for item in cached_data:
                        # Handle both dict and string responses from Redis
                        if isinstance(item, dict):
                            result.append(GoalResponse.model_validate(item))
                        else:
                            result.append(GoalResponse.parse_raw(item))
                    return result
            return None
        except Exception as e:
            logger.warning(
                f"Failed to get cached goals for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise APIServiceUnavailableError("Failed to get cached goals") from e
            
    async def _invalidate_goal_cache(self, user_id: UUID, goal_id: UUID) -> None:
        """Invalidate cache for a goal"""
        try:
            if self._redis:
                # Invalidate individual goal cache
                individual_cache_key = GoalCacheKey(user_id=user_id, goal_id=goal_id)
                await self._redis.delete(individual_cache_key.json())
                
                # Invalidate user's goals list cache
                # Use a string directly for the all goals cache key to avoid UUID validation
                all_goals_key = f"goal_cache:{user_id}:all"
                await self._redis.delete(all_goals_key)
        except Exception as e:
            logger.warning(
                f"Failed to invalidate cache for goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise APIServiceUnavailableError("Failed to invalidate cache") from e

    async def get_goal_analytics(self, goal_id: UUID, user_id: UUID) -> GoalAnalytics:
        """Get analytics for a goal."""
        from core.models.goal import Goal as GoalModel
        from datetime import datetime, timedelta

        # If we have a goal_id and user_id, fetch the goal model
        goal = await self.get_goal_by_id(goal_id, user_id)

        # Now goal is always a GoalModel with matched_deals relationship
        matched_deals = [
            MatchDetails(
                deal_id=match.deal_id,
                user_id=match.user_id,
                match_score=match.score,
                matched_at=match.matched_at
            )
            for match in goal.matched_deals
        ]

        # Calculate analytics
        notification_threshold = goal.notification_threshold or 0.8  # Default threshold if None
        active_matches = sum(1 for match in matched_deals if match.match_score >= notification_threshold)
        scores = [match.match_score for match in matched_deals]
        best_score = max(scores) if scores else None
        avg_score = sum(scores) / len(scores) if scores else None
        
        # Set the time period for analytics
        current_time = datetime.utcnow()
        start_date = goal.created_at if goal.created_at else current_time - timedelta(days=30)

        return GoalAnalytics(
            goal_id=goal_id,
            user_id=user_id,
            total_matches=len(matched_deals),
            active_matches=active_matches,
            matches_found=len(matched_deals),
            deals_processed=len(matched_deals),
            tokens_spent=0.0,  # Default value, would need actual token tracking
            rewards_earned=0.0,  # Default value, would need actual rewards tracking
            success_rate=0.0,  # Default value, would need to calculate
            best_match_score=best_score,
            average_match_score=avg_score,
            active_deals_count=active_matches,
            price_trends={},  # Default empty dict
            market_analysis={},  # Default empty dict
            deal_history=[],  # Default empty list
            performance_metrics={},  # Default empty dict
            start_date=start_date,
            end_date=current_time,
            period="monthly",  # Default period
            total_notifications=len([m for m in matched_deals if m.match_score >= notification_threshold]),
            last_checked=goal.last_checked_at,
            recent_matches=sorted(matched_deals, key=lambda x: x.matched_at, reverse=True)[:5]
        )

    async def _to_response(self, goal: GoalModel) -> GoalResponse:
        """
        Convert a Goal model to a GoalResponse
        """
        try:
            analytics = await self.get_goal_analytics(goal.id, goal.user_id)
        except Exception as e:
            logger.warning(f"Error getting goal analytics: {str(e)}")
            # Create a default GoalAnalytics object with all required fields
            from datetime import datetime, timedelta
            current_time = datetime.utcnow()
            analytics = GoalAnalytics(
                goal_id=goal.id,
                user_id=goal.user_id,
                total_matches=0,
                active_matches=0,
                matches_found=0,
                deals_processed=0,
                tokens_spent=0.0,
                rewards_earned=0.0,
                success_rate=0.0,
                best_match_score=None,
                average_match_score=None,
                active_deals_count=0,
                price_trends={},
                market_analysis={},
                deal_history=[],
                performance_metrics={},
                start_date=current_time - timedelta(days=30),  # Default to last 30 days
                end_date=current_time,
                period="monthly",
                total_notifications=0,
                last_checked=None,
                recent_matches=[]
            )

        return GoalResponse(
            id=goal.id,
            user_id=goal.user_id,
            title=goal.title,
            item_category=goal.item_category,
            constraints=goal.constraints,
            deadline=goal.deadline,
            status=goal.status,
            priority=goal.priority,
            max_matches=goal.max_matches,
            max_tokens=goal.max_tokens,
            notification_threshold=goal.notification_threshold,
            auto_buy_threshold=goal.auto_buy_threshold,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            last_checked_at=goal.last_checked_at,
            analytics=analytics
        )

    async def validate_goal_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate goal data according to business rules.
        
        Args:
            data: Goal data
            
        Returns:
            Dict[str, Any]: Validated goal data
            
        Raises:
            ValidationError: If goal data is invalid
        """
        try:
            # Validate status
            if "status" in data and data["status"] is not None:
                valid_statuses = [status.value for status in GoalStatus]
                if data["status"] not in valid_statuses:
                    valid_list = ", ".join(valid_statuses)
                    raise ValidationError(f"Invalid status. Must be one of: {valid_list}")
            
            # Validate priority
            if "priority" in data and data["priority"] is not None:
                # If priority is an integer, convert it to the enum value
                if isinstance(data["priority"], int):
                    # Map integer to enum value: 1->high, 2->medium, 3->low
                    priority_map = {
                        1: GoalPriority.HIGH.value,
                        2: GoalPriority.MEDIUM.value,
                        3: GoalPriority.LOW.value
                    }
                    if data["priority"] not in priority_map:
                        valid_values = list(priority_map.keys())
                        valid_list = ", ".join(str(val) for val in valid_values)
                        raise ValidationError(f"Invalid priority value: {data['priority']}. Must be one of: {valid_list}")
                    
                    # Store the original priority value for the response
                    data["original_priority"] = data["priority"]
                    # Convert to enum value for database storage
                    data["priority"] = priority_map[data["priority"]]
                    
                    # Log the conversion for debugging
                    logger.debug(f"Converted priority {data['original_priority']} to {data['priority']}")
                else:
                    # Handle string values
                    valid_priorities = [priority.value for priority in GoalPriority]
                    if data["priority"] not in valid_priorities:
                        valid_list = ", ".join(valid_priorities)
                        raise ValidationError(f"Invalid priority. Must be one of: {valid_list}")
            
            # Validate deadline
            if "deadline" in data and data["deadline"] is not None:
                now = datetime.now(timezone.utc)
                
                # Convert to timezone-aware
                if not data["deadline"].tzinfo:
                    data["deadline"] = data["deadline"].replace(tzinfo=timezone.utc)
                
                # Check that deadline is in the future
                if data["deadline"] <= now:
                    raise ValidationError("Deadline must be in the future")
                
                # Check that deadline is within limits
                max_deadline = now + timedelta(days=settings.MAX_GOAL_DEADLINE_DAYS)
                if data["deadline"] > max_deadline:
                    raise ValidationError(f"Deadline cannot exceed {settings.MAX_GOAL_DEADLINE_DAYS} days")
            
            # Validate constraints
            if "constraints" in data and data["constraints"] is not None:
                data["constraints"] = await self.validate_constraints(data["constraints"])
            
            # Validate max_matches
            if "max_matches" in data and data["max_matches"] is not None:
                if data["max_matches"] < 1:
                    raise ValidationError("max_matches must be greater than 0")
            
            # Validate max_tokens
            if "max_tokens" in data and data["max_tokens"] is not None:
                if data["max_tokens"] < 0:
                    raise ValidationError("max_tokens must be greater than or equal to 0")
                    
            # Validate thresholds
            if "notification_threshold" in data and data["notification_threshold"] is not None:
                if not 0 <= data["notification_threshold"] <= 1:
                    raise ValidationError("notification_threshold must be between 0 and 1")
                    
            if "auto_buy_threshold" in data and data["auto_buy_threshold"] is not None:
                if not 0 <= data["auto_buy_threshold"] <= 1:
                    raise ValidationError("auto_buy_threshold must be between 0 and 1")
            
            return data
        except Exception as e:
            logger.error(f"Goal data validation failed: {str(e)}")
            raise ValidationError(f"Invalid goal data: {str(e)}")

    async def validate_constraints(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Validate goal constraints according to business rules.
        
        Args:
            constraints: Dictionary containing constraint values
            
        Returns:
            Dict[str, Any]: Validated constraints
            
        Raises:
            ValidationError: If constraints are invalid
        """
        try:
            required_fields = ['min_price', 'max_price', 'keywords']
            
            # Handle the constraints format used in tests (with price_range)
            if 'price_range' in constraints:
                # Extract min_price and max_price from price_range
                if 'min' in constraints['price_range']:
                    constraints['min_price'] = constraints['price_range']['min']
                if 'max' in constraints['price_range']:
                    constraints['max_price'] = constraints['price_range']['max']
            
            # Check for missing fields
            missing_fields = [field for field in required_fields if field not in constraints]
            if missing_fields:
                error_msg = f"Missing required constraint fields: {', '.join(missing_fields)}"
                logger.error(f"Constraints validation failed: {error_msg}", extra={"constraints": constraints})
                raise ValidationError(error_msg)
            
            # Validate price constraints
            max_price = float(constraints['max_price'])
            min_price = float(constraints['min_price'])
            
            if max_price <= min_price:
                error_msg = "max_price must be greater than min_price"
                logger.error(f"Price validation failed: {error_msg}")
                raise ValidationError(error_msg)
            
            # Validate keywords
            if 'keywords' not in constraints or not constraints['keywords']:
                error_msg = "keywords cannot be empty"
                logger.error(f"Keywords validation failed: {error_msg}")
                raise ValidationError(error_msg)
            
            return constraints
        except ValidationError as e:
            # Re-raise validation errors with the same message
            raise
        except Exception as e:
            # Log and wrap other exceptions
            logger.error(f"Constraints validation failed: {str(e)}", extra={"constraints": constraints})
            raise ValidationError(f"Invalid constraints: {str(e)}")

    async def update_goal(
        self, 
        goal_id: UUID,
        **update_data
    ) -> GoalResponse:
        """Update a goal with cache invalidation
        
        Args:
            goal_id: Goal ID to update
            **update_data: Goal fields to update as keyword arguments
            
        Returns:
            GoalResponse: Updated goal
            
        Raises:
            GoalError: If update fails
            GoalNotFoundError: If goal not found
        """
        try:
            # Get the goal to verify it exists and get its user_id
            goal = await self.get_goal(goal_id)
            user_id = goal.user_id
            
            # Validate the goal data
            validated_data = await self.validate_goal_data(update_data)
            
            # Store original priority if present (for response)
            original_priority = None
            if "original_priority" in validated_data:
                original_priority = validated_data["original_priority"]
                # Remove original_priority from validated_data as it's not a database field
                del validated_data["original_priority"]
            
            # Create a copy of validated data for the database update
            database_update = validated_data.copy()
            
            # Update goal
            await self.session.execute(
                update(GoalModel)
                .where(GoalModel.id == goal_id)
                .values(**database_update, updated_at=datetime.utcnow())
            )
            await self.session.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(user_id, goal_id)
            
            # Get updated goal
            updated_goal = await self.get_goal(goal_id)
            
            # If we had an original_priority, modify the response to use it
            if original_priority is not None:
                updated_goal.priority = original_priority
            
            logger.info(
                f"Updated goal {goal_id}",
                extra={"goal_id": goal_id}
            )
            return updated_goal
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to update goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalError(f"Failed to update goal: {str(e)}") from e

    async def list_goals(
        self, user_id: Optional[UUID] = None, status: Optional[GoalStatus] = None, min_priority: Optional[int] = None
    ) -> List[GoalResponse]:
        """List goals with optional filters.

        Args:
            user_id: Optional user ID to filter goals by.
            status: Optional status to filter goals by.
            min_priority: Optional minimum priority to filter goals by.
                If set to 1, all goals are included (HIGH, MEDIUM, LOW priorities).
                If set to 2, only goals with MEDIUM and LOW priority are included.
                If set to 3, only goals with LOW priority are included.

        Returns:
            List of goal response objects.

        Raises:
            GoalError: If goal retrieval fails.
        """
        # Build query with joined loads for better performance
        query = select(GoalModel).options(
            joinedload(GoalModel.matched_deals)
        )

        if user_id:
            query = query.filter(GoalModel.user_id == user_id)

        if status:
            # Use the string value of the enum when filtering by status
            if isinstance(status, GoalStatus):
                query = query.filter(GoalModel.status == status.value)
            else:
                query = query.filter(GoalModel.status == status)

        try:
            # Execute the query to get all goals matching user_id and status filters
            result = await self.session.execute(query)
            goals = result.scalars().unique().all()
            
            # Now filter by priority in Python instead of SQL
            if min_priority is not None:
                filtered_goals = []
                
                # Define priority values for comparison                
                priority_high = "high"
                priority_medium = "medium"
                priority_low = "low"
                
                for goal in goals:
                    # Get the priority value regardless of whether it's an enum or string
                    goal_priority = goal.priority
                    if hasattr(goal_priority, 'value'):  # It's an enum
                        goal_priority = goal_priority.value
                    
                    # Convert to string if it's not already
                    if not isinstance(goal_priority, str):
                        goal_priority = str(goal_priority)
                    
                    if min_priority == 1:
                        # Include all priorities (HIGH, MEDIUM, LOW)
                        filtered_goals.append(goal)
                    elif min_priority == 2:
                        # Include only MEDIUM and LOW priorities
                        if goal_priority in [priority_medium, priority_low]:
                            filtered_goals.append(goal)
                    elif min_priority == 3:
                        # Include only LOW priority
                        if goal_priority == priority_low:
                            filtered_goals.append(goal)
                    else:
                        # Invalid min_priority, use default (all priorities)
                        logger.warning(f"Invalid min_priority value: {min_priority}. Using default (all priorities).")
                        filtered_goals.append(goal)
                
                goals = filtered_goals
            
            logger.info(f"Retrieved {len(goals)} goals. Filters: user_id={user_id}, status={status}, min_priority={min_priority}")
            return [await self._to_response(goal) for goal in goals]
        except Exception as e:
            logger.error(f"Failed to list goals: {str(e)}")
            raise GoalError(f"Failed to list goals: {str(e)}") from e

    async def get_goal_by_id(self, goal_id: UUID, user_id: Optional[UUID] = None) -> GoalModel:
        """
        Directly get a goal from the database without caching layer.
        This is used internally by analytics to ensure we have access to relationships.
        """
        query = select(GoalModel).filter(GoalModel.id == goal_id)
        
        if user_id:
            query = query.filter(GoalModel.user_id == user_id)
            
        result = await self.session.execute(query)
        goal = result.scalars().first()
        
        if not goal:
            raise GoalNotFoundError(f"Goal with id {goal_id} not found")
            
        return goal
