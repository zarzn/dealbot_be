"""Redis utilities module.

This module provides Redis functionality for caching, locking, and queuing operations.
"""

import json
import asyncio
from typing import Optional, Any, Dict
import redis.asyncio as aioredis
import logging
from ..config.redis import redis_settings
from core.exceptions.api_exceptions import RedisCacheError
logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[aioredis.BlockingConnectionPool] = None

async def get_redis_pool() -> aioredis.BlockingConnectionPool:
    """Get or create Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.BlockingConnectionPool(
                **redis_settings.get_connection_kwargs(),
                timeout=redis_settings.REDIS_POOL_TIMEOUT
            )
            logger.info("Redis connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {str(e)}")
            raise RedisCacheError(f"Redis pool initialization failed: {str(e)}")
    return _redis_pool

async def get_redis_client() -> aioredis.Redis:
    """Get Redis client from pool."""
    pool = await get_redis_pool()
    return aioredis.Redis(connection_pool=pool)

async def set_cache(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Set cache value with optional TTL."""
    try:
        async with await get_redis_client() as client:
            key = f"{redis_settings.REDIS_KEY_PREFIX}{key}"
            await client.set(
                key,
                json.dumps(value),
                ex=ttl or redis_settings.CACHE_DEFAULT_TTL
            )
    except (aioredis.RedisError, TypeError, ValueError) as e:
        logger.error(f"Failed to set cache for key {key}: {str(e)}")
        raise RedisCacheError(f"Cache set operation failed: {str(e)}")

async def get_cache(key: str) -> Optional[Any]:
    """Get cached value."""
    try:
        async with await get_redis_client() as client:
            key = f"{redis_settings.REDIS_KEY_PREFIX}{key}"
            value = await client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode cache value for key {key}: {str(e)}")
                await delete_cache(key)  # Clean up invalid JSON
        return None
    except aioredis.RedisError as e:
        logger.error(f"Failed to get cache for key {key}: {str(e)}")
        raise RedisCacheError(f"Cache get operation failed: {str(e)}")

async def delete_cache(key: str) -> None:
    """Delete cached value."""
    try:
        async with await get_redis_client() as client:
            key = f"{redis_settings.REDIS_KEY_PREFIX}{key}"
            await client.delete(key)
    except aioredis.RedisError as e:
        logger.error(f"Failed to delete cache for key {key}: {str(e)}")
        raise RedisCacheError(f"Cache delete operation failed: {str(e)}")

async def acquire_lock(
    lock_name: str,
    timeout: Optional[int] = None,
    blocking_timeout: Optional[int] = None
) -> Optional[aioredis.Redis]:
    """Acquire Redis lock."""
    try:
        client = await get_redis_client()
        lock_key = f"{redis_settings.REDIS_KEY_PREFIX}lock:{lock_name}"
        lock_timeout = timeout or redis_settings.LOCK_DEFAULT_TIMEOUT
        
        # Try to acquire lock using SET NX with expiry
        acquired = await client.set(
            lock_key,
            "1",
            nx=True,
            ex=lock_timeout
        )
        
        if acquired:
            return client
            
        if blocking_timeout:
            # If blocking timeout specified, wait and retry
            await asyncio.sleep(min(1, blocking_timeout))
            return await acquire_lock(lock_name, timeout, blocking_timeout - 1)
            
        return None
        
    except aioredis.RedisError as e:
        logger.error(f"Failed to acquire lock {lock_name}: {str(e)}")
        raise RedisCacheError(f"Lock acquisition failed: {str(e)}")

async def release_lock(lock_name: str, client: aioredis.Redis) -> None:
    """Release Redis lock."""
    try:
        lock_key = f"{redis_settings.REDIS_KEY_PREFIX}lock:{lock_name}"
        await client.delete(lock_key)
    except aioredis.RedisError as e:
        logger.error(f"Failed to release lock: {str(e)}")

async def enqueue(queue_name: str, data: Dict[str, Any]) -> None:
    """Add item to Redis queue."""
    try:
        async with await get_redis_client() as client:
            queue_key = f"{redis_settings.REDIS_KEY_PREFIX}queue:{queue_name}"
            await client.rpush(
                queue_key,
                json.dumps(data)
            )
    except (aioredis.RedisError, TypeError, ValueError) as e:
        logger.error(f"Failed to enqueue data to {queue_name}: {str(e)}")
        raise RedisCacheError(f"Queue operation failed: {str(e)}")

async def dequeue(queue_name: str) -> Optional[Dict[str, Any]]:
    """Get item from Redis queue."""
    try:
        async with await get_redis_client() as client:
            queue_key = f"{redis_settings.REDIS_KEY_PREFIX}queue:{queue_name}"
            data = await client.lpop(queue_key)
            if data is None:
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode queue data from {queue_name}: {str(e)}")
                return None
    except aioredis.RedisError as e:
        logger.error(f"Failed to dequeue from {queue_name}: {str(e)}")
        raise RedisCacheError(f"Queue operation failed: {str(e)}")

async def get_queue_length(queue_name: str) -> int:
    """Get queue length."""
    try:
        async with await get_redis_client() as client:
            queue_key = f"{redis_settings.REDIS_KEY_PREFIX}queue:{queue_name}"
            return await client.llen(queue_key)
    except aioredis.RedisError as e:
        logger.error(f"Failed to get queue length for {queue_name}: {str(e)}")
        raise RedisCacheError(f"Queue operation failed: {str(e)}")
