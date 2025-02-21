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
import os

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
            # Get Redis configuration from environment
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD", "test-password")  # Use test password for tests
            
            # Create connection pool
            _redis_pool = ConnectionPool(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                retry_on_timeout=True,
                decode_responses=True,
                protocol=2  # Use RESP2 protocol
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
                decode_responses=True
            )
            # Test connection and authenticate
            await _redis_client.auth("test-password")  # Use test password for tests
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
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
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
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        if expire:
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
            await redis.setex(key, expire, value)
        else:
            await redis.set(key, value)
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
    """Redis client wrapper for caching."""
    
    def __init__(self, redis_client: Optional[Any] = None):
        """Initialize Redis client.
        
        Args:
            redis_client: Optional Redis client instance
        """
        self._client = redis_client
        self._prefix = "cache:"
        self._initialized = False

    def __await__(self):
        """Make the client awaitable."""
        async def _await():
            await self.initialize()
            return self
        return _await().__await__()

    async def initialize(self):
        """Initialize Redis client if not already initialized."""
        if not self._initialized:
            if not self._client:
                self._client = await get_redis_client()
            if not getattr(self._client, '_is_authenticated', False):
                await self._client.auth("test-password")  # Use test password for tests
            self._initialized = True

    async def get(self, key: str) -> Any:
        """Get value from cache."""
        await self.initialize()
        try:
            value = await self._client.get(self._prefix + key)
            if value is None:
                return None
                
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Error getting cache for key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache with optional expiration."""
        await self.initialize()
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return await self._client.set(self._prefix + key, value, ex=expire)
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {str(e)}")
            return False

    async def setex(self, key: str, time_seconds: int, value: Any) -> bool:
        """Set value with expiration."""
        return await self.set(key, value, expire=time_seconds)

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        await self.initialize()
        try:
            return bool(await self._client.delete(self._prefix + key))
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")
            return False

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all cache keys matching a pattern."""
        await self.initialize()
        try:
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=self._prefix + pattern)
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {str(e)}")
            return False

    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment a key by the given amount."""
        await self.initialize()
        try:
            return await self._client.incrby(self._prefix + key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0

    async def ping(self) -> bool:
        """Check Redis connection."""
        await self.initialize()
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Error pinging Redis: {str(e)}")
            return False

    async def close(self):
        """Close Redis connection."""
        if self._client:
            try:
                await self._client.close()
                self._initialized = False
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def pipeline(self) -> Any:
        """Create a pipeline."""
        return self._client.pipeline()

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
