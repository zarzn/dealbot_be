from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy.exc import SQLAlchemyError
from redis.asyncio import Redis, ConnectionPool

from core.models.goal import Goal, GoalStatus
from core.models.user import User
from core.exceptions import (
    GoalError,
    GoalNotFoundError,
    GoalValidationError,
    DatabaseError,
    ValidationError
)
from core.repositories.base import BaseRepository
from core.config import settings
from core.utils.redis import get_redis_pool

logger = logging.getLogger(__name__)

class GoalRepository(BaseRepository):
    """Repository for managing Goal entities with async operations and caching"""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.redis_pool: Optional[ConnectionPool] = None

    async def init_redis(self) -> None:
        """Initialize Redis connection pool"""
        try:
            self.redis_pool = await get_redis_pool()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise RedisConnectionError("Failed to establish Redis connection") from e

    async def close_redis(self) -> None:
        """Close Redis connection pool"""
        try:
            if self.redis_pool:
                await self.redis_pool.close()
                await self.redis_pool.wait_closed()
                logger.info("Redis connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
            raise CacheOperationError("Failed to close Redis connection") from e

    async def create_goal(self, goal_data: Dict[str, Any]) -> Goal:
        """Create a new goal with caching"""
        try:
            goal = Goal(**goal_data)
            self.db.add(goal)
            await self.db.commit()
            await self.db.refresh(goal)
            
            # Cache the new goal
            await self._cache_goal(goal)
            
            logger.info(f"Created new goal {goal.id}")
            return goal
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            if "duplicate key" in str(e).lower():
                raise DuplicateRecordError("Goal already exists") from e
            logger.error(f"Failed to create goal: {str(e)}", exc_info=True)
            raise DatabaseError("Failed to create goal") from e

    async def get_goal_by_id(self, goal_id: UUID) -> Optional[Goal]:
        """Get a goal by ID with cache-first strategy"""
        try:
            # Try to get from cache first
            cached_goal = await self._get_cached_goal(goal_id)
            if cached_goal:
                logger.debug(f"Retrieved goal {goal_id} from cache")
                return cached_goal
                
            # Fallback to database
            result = await self.db.execute(
                select(Goal).where(Goal.id == goal_id)
            )
            goal = result.scalar_one_or_none()
            
            if goal:
                await self._cache_goal(goal)
                
            return goal
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve goal {goal_id}: {str(e)}", exc_info=True)
            raise DatabaseError("Failed to retrieve goal") from e

    async def get_user_goals(self, user_id: UUID) -> List[Goal]:
        """Get all goals for a user with caching"""
        try:
            # Try to get from cache first
            cached_goals = await self._get_cached_user_goals(user_id)
            if cached_goals:
                logger.debug(f"Retrieved goals for user {user_id} from cache")
                return cached_goals
                
            # Fallback to database
            result = await self.db.execute(
                select(Goal)
                .where(Goal.user_id == user_id)
                .order_by(Goal.created_at.desc())
            )
            goals = result.scalars().all()
            
            # Cache the results
            await self._cache_user_goals(user_id, goals)
            
            return goals
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve goals for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseError("Failed to retrieve user goals") from e

    async def update_goal(self, goal_id: UUID, update_data: Dict[str, Any]) -> Goal:
        """Update an existing goal with cache invalidation"""
        try:
            goal = await self.get_goal_by_id(goal_id)
            if not goal:
                raise RecordNotFoundError("Goal not found")

            for key, value in update_data.items():
                setattr(goal, key, value)

            await self.db.commit()
            await self.db.refresh(goal)
            
            # Invalidate cache
            await self._invalidate_goal_cache(goal_id)
            
            logger.info(f"Updated goal {goal_id}")
            return goal
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update goal {goal_id}: {str(e)}", exc_info=True)
            raise DatabaseError("Failed to update goal") from e

    async def delete_goal(self, goal_id: UUID) -> None:
        """Delete a goal with cache invalidation"""
        try:
            goal = await self.get_goal_by_id(goal_id)
            if not goal:
                raise RecordNotFoundError("Goal not found")

            await self.db.execute(
                delete(Goal).where(Goal.id == goal_id)
            )
            await self.db.commit()
            
            # Invalidate cache
            await self._invalidate_goal_cache(goal_id)
            
            logger.info(f"Deleted goal {goal_id}")
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to delete goal {goal_id}: {str(e)}", exc_info=True)
            raise DatabaseError("Failed to delete goal") from e

    async def get_active_goals(self) -> List[Goal]:
        """Get all active goals with caching"""
        try:
            # Try to get from cache first
            cached_goals = await self._get_cached_active_goals()
            if cached_goals:
                logger.debug("Retrieved active goals from cache")
                return cached_goals
                
            # Fallback to database
            result = await self.db.execute(
                select(Goal).where(Goal.status == 'active')
            )
            goals = result.scalars().all()
            
            # Cache the results
            await self._cache_active_goals(goals)
            
            return goals
            
        except SQLAlchemyError as e:
            logger.error("Failed to retrieve active goals", exc_info=True)
            raise DatabaseError("Failed to retrieve active goals") from e

    async def _cache_goal(self, goal: Goal) -> None:
        """Cache a single goal"""
        try:
            if self.redis_pool:
                await self.redis_pool.set(
                    f"goal:{goal.id}",
                    goal.json(),
                    ex=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(f"Failed to cache goal {goal.id}: {str(e)}")
            raise CacheOperationError("Failed to cache goal") from e

    async def _cache_user_goals(self, user_id: UUID, goals: List[Goal]) -> None:
        """Cache all goals for a user"""
        try:
            if self.redis_pool:
                await self.redis_pool.set(
                    f"user_goals:{user_id}",
                    [goal.json() for goal in goals],
                    ex=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(f"Failed to cache goals for user {user_id}: {str(e)}")
            raise CacheOperationError("Failed to cache user goals") from e

    async def _cache_active_goals(self, goals: List[Goal]) -> None:
        """Cache all active goals"""
        try:
            if self.redis_pool:
                await self.redis_pool.set(
                    "active_goals",
                    [goal.json() for goal in goals],
                    ex=settings.GOAL_CACHE_TTL
                )
        except Exception as e:
            logger.warning(f"Failed to cache active goals: {str(e)}")
            raise CacheOperationError("Failed to cache active goals") from e

    async def _get_cached_goal(self, goal_id: UUID) -> Optional[Goal]:
        """Get a cached goal"""
        try:
            if self.redis_pool:
                cached_data = await self.redis_pool.get(f"goal:{goal_id}")
                if cached_data:
                    return Goal.parse_raw(cached_data)
            return None
        except Exception as e:
            logger.warning(f"Failed to get cached goal {goal_id}: {str(e)}")
            raise CacheOperationError("Failed to get cached goal") from e

    async def _get_cached_user_goals(self, user_id: UUID) -> Optional[List[Goal]]:
        """Get cached goals for a user"""
        try:
            if self.redis_pool:
                cached_data = await self.redis_pool.get(f"user_goals:{user_id}")
                if cached_data:
                    return [Goal.parse_raw(data) for data in cached_data]
            return None
        except Exception as e:
            logger.warning(f"Failed to get cached goals for user {user_id}: {str(e)}")
            raise CacheOperationError("Failed to get cached user goals") from e

    async def _get_cached_active_goals(self) -> Optional[List[Goal]]:
        """Get cached active goals"""
        try:
            if self.redis_pool:
                cached_data = await self.redis_pool.get("active_goals")
                if cached_data:
                    return [Goal.parse_raw(data) for data in cached_data]
            return None
        except Exception as e:
            logger.warning(f"Failed to get cached active goals: {str(e)}")
            raise CacheOperationError("Failed to get cached active goals") from e

    async def _invalidate_goal_cache(self, goal_id: UUID) -> None:
        """Invalidate cache for a goal"""
        try:
            if self.redis_pool:
                # Invalidate individual goal cache
                await self.redis_pool.delete(f"goal:{goal_id}")
                
                # Invalidate active goals cache
                await self.redis_pool.delete("active_goals")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for goal {goal_id}: {str(e)}")
            raise CacheOperationError("Failed to invalidate cache") from e
