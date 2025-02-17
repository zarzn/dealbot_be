"""Redis utility module.

This module provides Redis client configuration and connection management.
"""

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from typing import Optional, Any, Union, Dict, List
import json
import logging
from datetime import timedelta, datetime
import time

from core.config import settings
from core.utils.logger import get_logger
from core.exceptions.base_exceptions import RateLimitError

logger = get_logger(__name__)

_redis_client: Optional[Redis] = None
_redis_pool: Optional[ConnectionPool] = None

async def get_redis_pool() -> ConnectionPool:
    """Get Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.ConnectionPool.from_url(
                str(settings.REDIS_URL),
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                retry_on_timeout=True
            )
            logger.info("Redis connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create Redis connection pool: {str(e)}")
            raise
    
    return _redis_pool

async def get_redis_client() -> Redis:
    """Get Redis client instance with connection pooling."""
    global _redis_client
    
    if _redis_client is None:
        try:
            pool = await get_redis_pool()
            _redis_client = Redis(
                connection_pool=pool,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    return _redis_client

async def close_redis_client() -> None:
    """Close Redis client connection and pool."""
    global _redis_client, _redis_pool
    
    if _redis_client is not None:
        try:
            await _redis_client.close()
            _redis_client = None
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
            raise
    
    if _redis_pool is not None:
        try:
            await _redis_pool.disconnect()
            _redis_pool = None
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection pool: {str(e)}")
            raise

# Function-based interface for simpler use cases
async def get_cache(key: str) -> Optional[Any]:
    """Get a value from Redis cache."""
    try:
        redis = await get_redis_client()
        value = await redis.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Error getting cache for key {key}: {str(e)}")
        return None

async def set_cache(
    key: str,
    value: Any,
    expire: Optional[Union[int, timedelta]] = None
) -> bool:
    """Set a value in Redis cache."""
    try:
        redis = await get_redis_client()
        serialized = json.dumps(value)
        if expire:
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
            await redis.setex(key, expire, serialized)
        else:
            await redis.set(key, serialized)
        return True
    except Exception as e:
        logger.error(f"Error setting cache for key {key}: {str(e)}")
        return False

async def delete_cache(key: str) -> bool:
    """Delete a value from Redis cache."""
    try:
        redis = await get_redis_client()
        await redis.delete(key)
        return True
    except Exception as e:
        logger.error(f"Error deleting cache for key {key}: {str(e)}")
        return False

# Class-based interface for more complex use cases
class RedisClient:
    """Redis client wrapper class."""
    
    _instance: Optional['RedisClient'] = None
    
    def __new__(cls) -> 'RedisClient':
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize Redis client."""
        if not hasattr(self, '_initialized') or not self._initialized:
            self._client = None
            self._pipeline = None
            self._initialized = True
    
    async def _get_client(self) -> Redis:
        """Get Redis client instance."""
        if self._client is None:
            self._client = await get_redis_client()
        return self._client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis cache."""
        try:
            redis = await self._get_client()
            value = await redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache for key {key}: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set a value in Redis cache."""
        try:
            redis = await self._get_client()
            serialized = json.dumps(value)
            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                await redis.setex(key, expire, serialized)
            else:
                await redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from Redis cache."""
        try:
            redis = await self._get_client()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")
            return False
    
    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all cache keys matching a pattern."""
        try:
            redis = await self._get_client()
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern)
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {str(e)}")
            return False
    
    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment a key by the given amount."""
        try:
            redis = await self._get_client()
            return await redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            redis = await self._get_client()
            return await redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {str(e)}")
            return False
    
    @property
    async def pipeline(self):
        """Get Redis pipeline."""
        if self._pipeline is None:
            redis = await self._get_client()
            self._pipeline = redis.pipeline()
        return self._pipeline
    
    async def close(self) -> None:
        """Close Redis client connection."""
        if self._client is not None:
            await close_redis_client()
            self._client = None
            self._pipeline = None

class RateLimit:
    """Rate limiting implementation using Redis."""

    def __init__(
        self,
        redis: Redis,
        key: str,
        limit: int,
        window: int = 60,
        precision: int = 60
    ):
        """Initialize rate limiter."""
        self.redis = redis
        self.key = key
        self.limit = limit
        self.window = window
        self.precision = precision
        self.redis_key = f"rate_limit:{key}"

    async def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit."""
        try:
            current = await self._get_counter()
            return current < self.limit
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return True

    async def increment(self) -> int:
        """Increment request counter."""
        try:
            current_time = int(time.time())
            pipeline = self.redis.pipeline()
            
            # Cleanup old counts
            pipeline.zremrangebyscore(
                self.redis_key,
                0,
                current_time - self.window
            )
            
            # Add new count
            pipeline.zadd(
                self.redis_key,
                {str(current_time): 1}
            )
            
            # Set expiration
            pipeline.expire(
                self.redis_key,
                self.window
            )
            
            await pipeline.execute()
            
            return await self._get_counter()
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {str(e)}")
            return 0

    async def get_reset_time(self) -> datetime:
        """Get time when rate limit will reset."""
        try:
            current_time = int(time.time())
            oldest = await self.redis.zrange(
                self.redis_key,
                0,
                0,
                withscores=True
            )
            if not oldest:
                return datetime.fromtimestamp(current_time)
            
            oldest_time = int(float(oldest[0][1]))
            reset_time = oldest_time + self.window
            
            return datetime.fromtimestamp(reset_time)
        except Exception as e:
            logger.error(f"Error getting rate limit reset time: {str(e)}")
            return datetime.fromtimestamp(time.time() + self.window)

    async def _get_counter(self) -> int:
        """Get current request count."""
        try:
            current_time = int(time.time())
            count = await self.redis.zcount(
                self.redis_key,
                current_time - self.window,
                current_time
            )
            return count
        except Exception as e:
            logger.error(f"Error getting rate limit counter: {str(e)}")
            return 0

    async def reset(self) -> None:
        """Reset rate limit counter."""
        try:
            await self.redis.delete(self.redis_key)
        except Exception as e:
            logger.error(f"Error resetting rate limit: {str(e)}")

    async def get_remaining(self) -> int:
        """Get remaining requests allowed."""
        try:
            current = await self._get_counter()
            return max(0, self.limit - current)
        except Exception as e:
            logger.error(f"Error getting remaining rate limit: {str(e)}")
            return 0

    async def check_limit(self) -> None:
        """Check rate limit and raise error if exceeded."""
        if not await self.is_allowed():
            reset_time = await self.get_reset_time()
            raise RateLimitError(
                "Rate limit exceeded",
                reset_time=reset_time
            )
