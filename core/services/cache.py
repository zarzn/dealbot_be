"""Cache service for centralized caching operations."""

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union
from redis.asyncio import Redis

from core.exceptions import CacheError

logger = logging.getLogger(__name__)

class CacheService:
    """Centralized cache service for all caching operations."""

    def __init__(self, redis_client: Redis):
        """Initialize cache service with Redis client."""
        self._client = redis_client
        self._prefix = "cache:"

    async def get(self, key: str) -> Any:
        """Get value from cache."""
        try:
            value = await self._client.get(self._prefix + key)
            if value is None:
                return None

            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            raise CacheError(
                message=f"Cache get operation failed: {str(e)}",
                cache_key=key,
                operation="get"
            )

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with optional expiration."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if expire:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                return await self._client.setex(self._prefix + key, expire, value)
            return await self._client.set(self._prefix + key, value)
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            raise CacheError(
                message=f"Cache set operation failed: {str(e)}",
                cache_key=key,
                operation="set"
            )

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return bool(await self._client.delete(self._prefix + key))
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            raise CacheError(
                message=f"Cache delete operation failed: {str(e)}",
                cache_key=key,
                operation="delete"
            )

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return await self._client.exists(self._prefix + key)
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {str(e)}")
            raise CacheError(
                message=f"Cache exists operation failed: {str(e)}",
                cache_key=key,
                operation="exists"
            )

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
            logger.error(f"Error clearing cache pattern {pattern}: {str(e)}")
            raise CacheError(
                message=f"Cache pattern clear failed: {str(e)}",
                cache_key=pattern,
                operation="clear_pattern"
            )

    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment key by amount."""
        try:
            return await self._client.incrby(self._prefix + key, amount)
        except Exception as e:
            logger.error(f"Error incrementing cache key {key}: {str(e)}")
            raise CacheError(
                message=f"Cache increment operation failed: {str(e)}",
                cache_key=key,
                operation="incrby"
            )

    async def pipeline(self) -> Any:
        """Create Redis pipeline."""
        try:
            return await self._client.pipeline()
        except Exception as e:
            logger.error(f"Error creating cache pipeline: {str(e)}")
            raise CacheError(
                message=f"Cache pipeline creation failed: {str(e)}",
                cache_key="pipeline",
                operation="pipeline"
            )

    async def ping(self) -> bool:
        """Check cache connection."""
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Error pinging cache: {str(e)}")
            return False

    async def close(self) -> None:
        """Close cache connection."""
        try:
            await self._client.close()
        except Exception as e:
            logger.error(f"Error closing cache connection: {str(e)}")
            raise CacheError(
                message=f"Cache close operation failed: {str(e)}",
                cache_key="connection",
                operation="close"
            )

    async def flushdb(self) -> bool:
        """Clear all data in the current database."""
        try:
            return await self._client.flushdb()
        except Exception as e:
            logger.error(f"Error flushing cache database: {str(e)}")
            raise CacheError(
                message=f"Cache database flush failed: {str(e)}",
                cache_key="database",
                operation="flushdb"
            )

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to list head."""
        try:
            return await self._client.lpush(self._prefix + key, *values)
        except Exception as e:
            logger.error(f"Error pushing to cache list {key}: {str(e)}")
            raise CacheError(
                message=f"Cache list push failed: {str(e)}",
                cache_key=key,
                operation="lpush"
            )

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to list tail."""
        try:
            return await self._client.rpush(self._prefix + key, *values)
        except Exception as e:
            logger.error(f"Error pushing to cache list {key}: {str(e)}")
            raise CacheError(
                message=f"Cache list push failed: {str(e)}",
                cache_key=key,
                operation="rpush"
            )

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get range of values from list."""
        try:
            return await self._client.lrange(self._prefix + key, start, end)
        except Exception as e:
            logger.error(f"Error getting range from cache list {key}: {str(e)}")
            raise CacheError(
                message=f"Cache list range failed: {str(e)}",
                cache_key=key,
                operation="lrange"
            )

    async def scan(self, cursor: int = 0, match: Optional[str] = None) -> tuple[int, list[str]]:
        """Scan keys matching pattern."""
        try:
            return await self._client.scan(cursor, match=match)
        except Exception as e:
            logger.error(f"Error scanning cache keys with pattern {match}: {str(e)}")
            raise CacheError(
                message=f"Cache scan operation failed: {str(e)}",
                cache_key=match or "*",
                operation="scan"
            ) 