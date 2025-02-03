"""Redis cache utility.

This module provides a Redis cache implementation for the application.
"""

import json
import logging
from typing import Optional, Any, Dict, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Asynchronous Redis cache implementation."""
    
    def __init__(
        self,
        prefix: str,
        url: str = settings.REDIS_URL,
        pool_size: int = 10,
        socket_timeout: int = 5
    ):
        """Initialize Redis cache.
        
        Args:
            prefix: Cache key prefix
            url: Redis connection URL
            pool_size: Connection pool size
            socket_timeout: Socket timeout in seconds
        """
        self.prefix = prefix
        self.pool = ConnectionPool.from_url(
            url,
            max_connections=pool_size,
            socket_timeout=socket_timeout,
            decode_responses=True
        )
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get Redis client instance.
        
        Returns:
            Redis client instance
            
        Raises:
            CacheConnectionError: If connection fails
        """
        if not self._redis:
            try:
                self._redis = redis.Redis(connection_pool=self.pool)
                await self._redis.ping()
            except RedisError as e:
                raise CacheConnectionError(
                    message="Failed to connect to Redis",
                    details={"error": str(e)}
                )
        return self._redis

    def _make_key(self, key: str) -> str:
        """Create prefixed cache key.
        
        Args:
            key: Original key
            
        Returns:
            Prefixed key
        """
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found, None otherwise
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(self._make_key(key))
            
            if value is None:
                return None
                
            return json.loads(value)
            
        except json.JSONDecodeError as e:
            raise CacheOperationError(
                message="Failed to decode cached value",
                details={"key": key, "error": str(e)}
            )
        except RedisError as e:
            raise CacheOperationError(
                message="Cache get operation failed",
                details={"key": key, "error": str(e)}
            )

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None
    ) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds or timedelta
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            serialized = json.dumps(value)
            
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
                
            await redis_client.set(
                self._make_key(key),
                serialized,
                ex=expire
            )
            
        except (TypeError, json.JSONEncodeError) as e:
            raise CacheOperationError(
                message="Failed to serialize value",
                details={"key": key, "error": str(e)}
            )
        except RedisError as e:
            raise CacheOperationError(
                message="Cache set operation failed",
                details={"key": key, "error": str(e)}
            )

    async def delete(self, key: str) -> None:
        """Delete value from cache.
        
        Args:
            key: Cache key
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            await redis_client.delete(self._make_key(key))
            
        except RedisError as e:
            raise CacheOperationError(
                message="Cache delete operation failed",
                details={"key": key, "error": str(e)}
            )

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            return await redis_client.exists(self._make_key(key)) > 0
            
        except RedisError as e:
            raise CacheOperationError(
                message="Cache exists operation failed",
                details={"key": key, "error": str(e)}
            )

    async def increment(
        self,
        key: str,
        amount: int = 1,
        expire: Optional[Union[int, timedelta]] = None
    ) -> int:
        """Increment counter in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            expire: Expiration time in seconds or timedelta
            
        Returns:
            New counter value
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key(key)
            
            if not await redis_client.exists(key):
                await redis_client.set(key, 0)
                
            value = await redis_client.incrby(key, amount)
            
            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                await redis_client.expire(key, expire)
                
            return value
            
        except RedisError as e:
            raise CacheOperationError(
                message="Cache increment operation failed",
                details={"key": key, "error": str(e)}
            )

    async def clear_prefix(self) -> None:
        """Clear all keys with current prefix.
        
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            redis_client = await self._get_redis()
            pattern = f"{self.prefix}:*"
            
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await redis_client.delete(*keys)
                    
                if cursor == 0:
                    break
                    
        except RedisError as e:
            raise CacheOperationError(
                message="Cache clear operation failed",
                details={"prefix": self.prefix, "error": str(e)}
            )

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        await self.pool.disconnect() 