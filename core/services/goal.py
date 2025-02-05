from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from pydantic import BaseModel
from fastapi import BackgroundTasks
from datetime import datetime
import json

from core.models.goal import GoalCreate, GoalResponse, GoalUpdate
from core.models.database import Goal as GoalModel
from core.models.goal_types import GoalStatus
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
from core.tasks.goal_tasks import update_goal_status_task

logger = logging.getLogger(__name__)

class GoalCacheKey(BaseModel):
    user_id: UUID
    goal_id: UUID

class GoalService:
    """Service layer for goal management operations"""
    
    def __init__(
        self, 
        db: AsyncSession, 
        token_service: TokenService,
        background_tasks: Optional[BackgroundTasks] = None
    ):
        self.db = db
        self.token_service = token_service
        self.background_tasks = background_tasks
        self.redis_client = None
        
    async def init_redis(self) -> None:
        """Initialize Redis connection with retry mechanism"""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self.redis_client = await get_redis_client()
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
            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
            raise APIServiceUnavailableError("Failed to close Redis connection") from e

    async def create_goal(
        self, 
        user_id: UUID, 
        goal: GoalCreate,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> GoalResponse:
        """Create a new goal with token validation and caching"""
        try:
            # Validate token balance
            await self.token_service.validate_goal_creation(user_id)
            
            # Create goal
            db_goal = GoalModel(
                user_id=user_id,
                **goal.dict(exclude_unset=True),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(db_goal)
            await self.db.commit()
            await self.db.refresh(db_goal)
            
            # Cache the new goal
            await self._cache_goal(db_goal)
            
            # Schedule background status update check if needed
            if background_tasks and self.background_tasks:
                self.background_tasks.add_task(
                    "update_goal_status",
                    goal_id=db_goal.id,
                    user_id=user_id
                )
                
            logger.info(
                f"Created new goal {db_goal.id} for user {user_id}",
                extra={"goal_id": db_goal.id, "user_id": user_id}
            )
            return GoalResponse.from_orm(db_goal)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to create goal for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise InvalidGoalDataError(f"Failed to create goal: {str(e)}") from e

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
            result = await self.db.execute(
                select(GoalModel)
                .where(GoalModel.user_id == user_id)
                .order_by(GoalModel.created_at.desc())
            )
            goals = result.scalars().all()
            
            # Cache the results
            await self._cache_goals(user_id, goals)
            
            logger.debug(
                f"Retrieved {len(goals)} goals from database for user {user_id}",
                extra={"user_id": user_id}
            )
            return [GoalResponse.from_orm(goal) for goal in goals]
        except Exception as e:
            logger.error(
                f"Failed to get goals for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise GoalNotFoundError(f"Failed to get goals: {str(e)}") from e

    async def get_goal(self, user_id: UUID, goal_id: UUID) -> GoalResponse:
        """Get a specific goal with caching"""
        try:
            # Try to get from cache first
            cached_goal = await self._get_cached_goal(user_id, goal_id)
            if cached_goal:
                logger.debug(
                    f"Retrieved goal {goal_id} from cache for user {user_id}",
                    extra={"goal_id": goal_id, "user_id": user_id}
                )
                return cached_goal
                
            # Fallback to database
            result = await self.db.execute(
                select(GoalModel)
                .where(GoalModel.id == goal_id)
                .where(GoalModel.user_id == user_id)
            )
            goal = result.scalar_one_or_none()
            if not goal:
                raise GoalNotFoundError(f"Goal {goal_id} not found")
                
            # Cache the result
            await self._cache_goal(goal)
            
            logger.debug(
                f"Retrieved goal {goal_id} from database for user {user_id}",
                extra={"goal_id": goal_id, "user_id": user_id}
            )
            return GoalResponse.from_orm(goal)
        except Exception as e:
            logger.error(
                f"Failed to get goal {goal_id} for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id, "user_id": user_id}
            )
            raise GoalNotFoundError(f"Failed to get goal: {str(e)}") from e

    async def update_goal_status(
        self, 
        user_id: UUID,
        goal_id: UUID, 
        status: str,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> GoalResponse:
        """Update goal status with validation and cache invalidation"""
        if status not in GoalStatus.list():
            raise InvalidGoalDataError(
                f"Invalid status. Must be one of: {', '.join(GoalStatus.list())}"
            )
            
        try:
            # Get and validate goal
            goal = await self.get_goal(user_id, goal_id)
            
            # Update status
            await self.db.execute(
                update(GoalModel)
                .where(GoalModel.id == goal_id)
                .values(status=status, updated_at=datetime.utcnow())
            )
            await self.db.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(user_id, goal_id)
            
            # Schedule background status update check if needed
            if background_tasks and self.background_tasks:
                self.background_tasks.add_task(
                    "update_goal_status",
                    goal_id=goal_id,
                    user_id=user_id
                )
                
            logger.info(
                f"Updated goal {goal_id} status to {status}",
                extra={"goal_id": goal_id, "status": status}
            )
            return GoalResponse.from_orm(goal)
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to update goal {goal_id} status: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalError(f"Failed to update goal status: {str(e)}") from e

    async def delete_goal(self, user_id: UUID, goal_id: UUID) -> None:
        """Delete a goal with cache invalidation"""
        try:
            # Get and validate goal
            await self.get_goal(user_id, goal_id)
            
            # Delete goal
            await self.db.execute(
                delete(GoalModel)
                .where(GoalModel.id == goal_id)
            )
            await self.db.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(user_id, goal_id)
            
            logger.info(
                f"Deleted goal {goal_id} for user {user_id}",
                extra={"goal_id": goal_id, "user_id": user_id}
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to delete goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise GoalNotFoundError(f"Failed to delete goal: {str(e)}") from e
            
    async def _cache_goal(self, goal: GoalModel) -> None:
        """Cache a single goal"""
        try:
            if self.redis_client:
                cache_key = GoalCacheKey(user_id=goal.user_id, goal_id=goal.id)
                await self.redis_client.set(
                    cache_key.json(),
                    GoalResponse.from_orm(goal).json(),
                    ex=settings.GOAL_CACHE_TTL
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
            if self.redis_client:
                cache_key = GoalCacheKey(user_id=user_id, goal_id="all")
                await self.redis_client.set(
                    cache_key.json(),
                    [GoalResponse.from_orm(goal).json() for goal in goals],
                    ex=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(
                f"Failed to cache goals for user {user_id}: {str(e)}",
                exc_info=True,
                extra={"user_id": user_id}
            )
            raise APIServiceUnavailableError("Failed to cache goals") from e
            
    async def _get_cached_goal(self, user_id: UUID, goal_id: UUID) -> Optional[GoalResponse]:
        """Get a cached goal"""
        try:
            if self.redis_client:
                cache_key = GoalCacheKey(user_id=user_id, goal_id=goal_id)
                cached_data = await self.redis_client.get(cache_key.json())
                if cached_data:
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
            if self.redis_client:
                cache_key = GoalCacheKey(user_id=user_id, goal_id="all")
                cached_data = await self.redis_client.get(cache_key.json())
                if cached_data:
                    return [GoalResponse.parse_raw(data) for data in cached_data]
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
            if self.redis_client:
                # Invalidate individual goal cache
                cache_key = GoalCacheKey(user_id=user_id, goal_id=goal_id)
                await self.redis_client.delete(cache_key.json())
                
                # Invalidate user's goals list cache
                cache_key = GoalCacheKey(user_id=user_id, goal_id="all")
                await self.redis_client.delete(cache_key.json())
        except Exception as e:
            logger.warning(
                f"Failed to invalidate cache for goal {goal_id}: {str(e)}",
                exc_info=True,
                extra={"goal_id": goal_id}
            )
            raise APIServiceUnavailableError("Failed to invalidate cache") from e
