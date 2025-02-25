"""Redis service for centralized Redis operations."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List, Tuple
from redis.asyncio import Redis, ConnectionPool

from core.config import settings
from core.exceptions import RedisError

logger = logging.getLogger(__name__)

class RedisService:
    """Centralized Redis service for all Redis operations."""

    _instance = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None

    def __new__(cls):
        """Singleton pattern to ensure only one Redis service instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Redis service."""
        self._prefix = "cache:"

    @classmethod
    async def get_instance(cls) -> 'RedisService':
        """Get Redis service instance."""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.init()
        return cls._instance

    async def init(self, client: Optional[Redis] = None) -> None:
        """Initialize Redis client."""
        if client:
            self._client = client
            return

        if self._client is None:
            try:
                pool = await self._get_pool()
                self._client = Redis(connection_pool=pool)
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {str(e)}")
                raise RedisError(f"Redis initialization failed: {str(e)}")

    async def _get_pool(self) -> ConnectionPool:
        """Get Redis connection pool."""
        if self._pool is None:
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

                if hasattr(settings, "REDIS_SOCKET_KEEPALIVE"):
                    pool_kwargs["socket_keepalive"] = settings.REDIS_SOCKET_KEEPALIVE

                if hasattr(settings, "REDIS_SOCKET_KEEPALIVE_OPTIONS"):
                    pool_kwargs["socket_keepalive_options"] = settings.REDIS_SOCKET_KEEPALIVE_OPTIONS

                self._pool = ConnectionPool.from_url(
                    str(settings.REDIS_URL),
                    **pool_kwargs
                )
            except Exception as e:
                logger.error(f"Failed to create Redis connection pool: {str(e)}")
                raise RedisError(f"Redis pool creation failed: {str(e)}")

        return self._pool

    async def close(self) -> None:
        """Close Redis connections."""
        if self._client:
            try:
                await self._client.close()
                self._client = None
            except Exception as e:
                logger.error(f"Error closing Redis client: {str(e)}")

        if self._pool:
            try:
                await self._pool.disconnect()
                self._pool = None
            except Exception as e:
                logger.error(f"Error closing Redis pool: {str(e)}")

    async def flushdb(self) -> bool:
        """Clear all data in the current database."""
        try:
            return await self._client.flushdb()
        except Exception as e:
            logger.error(f"Error flushing Redis database: {str(e)}")
            raise RedisError(f"Redis database flush failed: {str(e)}")

    async def get(self, key: str) -> Any:
        """Get value from Redis."""
        try:
            value = await self._client.get(self._prefix + key)
            if value is None:
                return None

            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Error getting Redis key {key}: {str(e)}")
            raise RedisError(f"Redis get operation failed: {str(e)}")

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in Redis with optional expiration."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                return await self._client.setex(self._prefix + key, expire, value)
            return await self._client.set(self._prefix + key, value)
        except Exception as e:
            logger.error(f"Error setting Redis key {key}: {str(e)}")
            raise RedisError(f"Redis set operation failed: {str(e)}")

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            return bool(await self._client.delete(self._prefix + key))
        except Exception as e:
            logger.error(f"Error deleting Redis key {key}: {str(e)}")
            raise RedisError(f"Redis delete operation failed: {str(e)}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            return await self._client.exists(self._prefix + key)
        except Exception as e:
            logger.error(f"Error checking Redis key {key}: {str(e)}")
            raise RedisError(f"Redis exists operation failed: {str(e)}")

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching pattern."""
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
            logger.error(f"Error clearing Redis pattern {pattern}: {str(e)}")
            raise RedisError(f"Redis pattern clear failed: {str(e)}")

    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment key by amount."""
        try:
            return await self._client.incrby(self._prefix + key, amount)
        except Exception as e:
            logger.error(f"Error incrementing Redis key {key}: {str(e)}")
            raise RedisError(f"Redis increment operation failed: {str(e)}")

    async def ping(self) -> bool:
        """Check Redis connection."""
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Error pinging Redis: {str(e)}")
            return False

    # Token blacklist operations
    async def blacklist_token(self, token: str, expire: int) -> bool:
        """Add token to blacklist."""
        try:
            key = f"blacklist:{token}"
            return await self._client.setex(key, expire, "1")
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            raise RedisError(f"Token blacklist operation failed: {str(e)}")

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        try:
            key = f"blacklist:{token}"
            return bool(await self._client.exists(key))
        except Exception as e:
            logger.error(f"Error checking blacklisted token: {str(e)}")
            raise RedisError(f"Token blacklist check failed: {str(e)}")

    # Rate limiting operations
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, int]:
        """Check rate limit for key.
        
        Returns:
            Tuple[bool, int]: (is_allowed, current_count)
        """
        try:
            pipeline = self._client.pipeline()
            now = datetime.utcnow().timestamp()
            window_start = now - window
            
            key = f"rate_limit:{key}"
            await pipeline.zremrangebyscore(key, 0, window_start)
            await pipeline.zadd(key, {str(now): now})
            await pipeline.zcard(key)
            await pipeline.expire(key, window)
            
            results = await pipeline.execute()
            count = results[2]
            
            return count <= limit, count
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            raise RedisError(f"Rate limit check failed: {str(e)}")

    # Pipeline operations
    async def pipeline(self) -> Any:
        """Create Redis pipeline."""
        try:
            return self._client.pipeline()
        except Exception as e:
            logger.error(f"Error creating Redis pipeline: {str(e)}")
            raise RedisError(f"Redis pipeline creation failed: {str(e)}")

    # List operations
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to list head."""
        try:
            return await self._client.lpush(self._prefix + key, *values)
        except Exception as e:
            logger.error(f"Error pushing to Redis list {key}: {str(e)}")
            raise RedisError(f"Redis list push failed: {str(e)}")

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to list tail."""
        try:
            return await self._client.rpush(self._prefix + key, *values)
        except Exception as e:
            logger.error(f"Error pushing to Redis list {key}: {str(e)}")
            raise RedisError(f"Redis list push failed: {str(e)}")

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get range of values from list."""
        try:
            return await self._client.lrange(self._prefix + key, start, end)
        except Exception as e:
            logger.error(f"Error getting range from Redis list {key}: {str(e)}")
            raise RedisError(f"Redis list range failed: {str(e)}")

# Global instance
redis_service: Optional[RedisService] = None

async def get_redis_service() -> RedisService:
    """Get Redis service instance."""
    global redis_service
    if redis_service is None:
        redis_service = await RedisService.get_instance()
    return redis_service 