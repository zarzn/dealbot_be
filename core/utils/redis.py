"""Redis utility module.

This module provides Redis client configuration and connection management.
"""

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from typing import Optional, Any, Union
import json
import logging
from datetime import timedelta

from core.config import settings

logger = logging.getLogger(__name__)

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

async def set_cache(key: str, value: Any, expire: Optional[Union[int, timedelta]] = None) -> bool:
    """Set a value in Redis cache.
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        expire: Expiration time in seconds or timedelta
        
    Returns:
        bool: True if successful, False otherwise
    """
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

async def get_cache(key: str) -> Optional[Any]:
    """Get a value from Redis cache.
    
    Args:
        key: Cache key
        
    Returns:
        Optional[Any]: Cached value if exists, None otherwise
    """
    try:
        redis = await get_redis_client()
        value = await redis.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Error getting cache for key {key}: {str(e)}")
        return None

async def delete_cache(key: str) -> bool:
    """Delete a value from Redis cache.
    
    Args:
        key: Cache key
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis = await get_redis_client()
        await redis.delete(key)
        return True
    except Exception as e:
        logger.error(f"Error deleting cache for key {key}: {str(e)}")
        return False

async def clear_cache_pattern(pattern: str) -> bool:
    """Clear all cache keys matching a pattern.
    
    Args:
        pattern: Redis key pattern to match
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        redis = await get_redis_client()
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
