"""Redis utilities."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from redis.asyncio import Redis, ConnectionPool
from core.config import settings

logger = logging.getLogger(__name__)

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None

async def get_redis_pool() -> ConnectionPool:
    """Get Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is None:
        try:
            pool_kwargs = {
                "max_connections": getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                "socket_timeout": getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                "socket_connect_timeout": getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                "retry_on_timeout": getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                "health_check_interval": getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                "decode_responses": True,
                "encoding": "utf-8"
            }
            
            # Optional settings
            if hasattr(settings, "REDIS_SOCKET_KEEPALIVE"):
                pool_kwargs["socket_keepalive"] = settings.REDIS_SOCKET_KEEPALIVE
                
            if hasattr(settings, "REDIS_SOCKET_KEEPALIVE_OPTIONS"):
                pool_kwargs["socket_keepalive_options"] = settings.REDIS_SOCKET_KEEPALIVE_OPTIONS
            
            _redis_pool = ConnectionPool.from_url(
                str(settings.REDIS_URL),
                **pool_kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create Redis connection pool: {str(e)}")
            raise
    
    return _redis_pool

async def get_redis_client() -> Redis:
    """Get Redis client."""
    global _redis_client
    
    if _redis_client is None:
        try:
            pool = await get_redis_pool()
            _redis_client = Redis(connection_pool=pool)
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    return _redis_client

async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None

async def close_redis_pool() -> None:
    """Close Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None

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
    
    def __init__(self):
        """Initialize Redis client."""
        self._client = None
        self._prefix = "cache:"

    async def init(self, client=None):
        """Initialize the Redis client asynchronously.
        
        Args:
            client: Optional Redis client for testing
        """
        if self._client is None:
            if client is not None:
                self._client = client
            else:
                self._client = await get_redis_client()
        return self

    async def get(self, key: str) -> Any:
        """Get value from cache."""
        if self._client is None:
            await self.init()
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
        if self._client is None:
            await self.init()
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            if expire:
                return await self._client.setex(self._prefix + key, expire, value)
            return await self._client.set(self._prefix + key, value)
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {str(e)}")
            return False

    async def setex(self, key: str, time_seconds: int, value: Any) -> bool:
        """Set value with expiration."""
        return await self.set(key, value, expire=time_seconds)

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if self._client is None:
            await self.init()
        try:
            return bool(await self._client.delete(self._prefix + key))
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")
            return False

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all cache keys matching a pattern."""
        if self._client is None:
            await self.init()
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
        if self._client is None:
            await self.init()
        try:
            return await self._client.incrby(self._prefix + key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0

    async def ping(self) -> bool:
        """Check Redis connection."""
        if self._client is None:
            await self.init()
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Error pinging Redis: {str(e)}")
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            try:
                await self._client.close()
                self._client = None
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")

    async def pipeline(self) -> Any:
        """Create a pipeline."""
        if self._client is None:
            await self.init()
        return self._client.pipeline()

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the head of a list."""
        if self._client is None:
            await self.init()
        try:
            return await self._client.lpush(self._prefix + key, *values)
        except Exception as e:
            logger.error(f"Error pushing to list {key}: {str(e)}")
            return 0

class RateLimit:
    """Rate limiting implementation using Redis."""
    
    def __init__(self, redis_client: Any, key: str, limit: int, window: int):
        """Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance
            key: Rate limit key
            limit: Maximum number of requests
            window: Time window in seconds
        """
        self._redis = redis_client
        self._key = f"rate_limit:{key}"
        self._limit = limit
        self._window = window

    async def is_allowed(self) -> bool:
        """Check if request is allowed."""
        try:
            pipeline = await self._redis.pipeline()
            now = time.time()
            
            # Remove old entries
            await pipeline.zremrangebyscore(
                self._key,
                0,
                now - self._window
            )
            
            # Count current requests
            count = await pipeline.zcard(self._key)
            results = await pipeline.execute()
            
            # Get the actual count from results
            current_count = results[-1] if results else 0
            
            return current_count < self._limit
        except Exception as e:
            logger.error(f"Error getting rate limit counter: {str(e)}")
            return False

    async def increment(self) -> None:
        """Increment request counter."""
        try:
            pipeline = await self._redis.pipeline()
            now = time.time()
            
            # Add new request
            await pipeline.zadd(self._key, {str(now): now})
            
            # Set expiration
            await pipeline.expire(self._key, self._window)
            
            await pipeline.execute()
        except Exception as e:
            logger.error(f"Error incrementing rate limit counter: {str(e)}")

    async def check_limit(self) -> None:
        """Check rate limit and raise error if exceeded."""
        if not await self.is_allowed():
            now = time.time()
            reset_at = datetime.fromtimestamp(now + self._window)
            raise RateLimitError("Rate limit exceeded", limit=self._limit, reset_at=reset_at)
