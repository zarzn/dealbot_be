from typing import Optional, Callable, Any, TypeVar, Coroutine, List, Dict, Union
from functools import wraps
from fastapi import HTTPException
from backend.core.config import settings
from backend.core.exceptions import RedisConnectionError
import json
import logging
import asyncio
from redis.asyncio import Redis, ConnectionPool
import os
from datetime import datetime, timedelta
import aioredis
from aioredis.client import Redis

from .logger import get_logger

logger = get_logger(__name__)

# Type variable for generic function return type
F = TypeVar('F', bound=Callable[..., Coroutine[Any, Any, Any]])

# Redis connection pool
_redis_pool: Optional[Redis] = None

class RedisClient:
    """Redis client wrapper with connection pooling and pub/sub support"""
    
    _instance: Optional[Redis] = None
    DEFAULT_TTL = 3600  # 1 hour
    MAX_CONNECTIONS = 20
    MIN_CONNECTIONS = 5
    
    @classmethod
    async def get_redis(cls) -> Redis:
        """Get Redis connection from pool"""
        if cls._instance is None:
            try:
                cls._instance = Redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=cls.MAX_CONNECTIONS,
                    min_connections=cls.MIN_CONNECTIONS
                )
                await cls._instance.ping()  # Test connection
            except Exception as e:
                logger.error(f"Redis connection error: {str(e)}")
                raise RedisConnectionError(f"Redis connection error: {str(e)}")
        return cls._instance

    @classmethod
    async def close_redis(cls):
        """Close Redis connection"""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None

    @classmethod
    async def get_pubsub(cls) -> Redis:
        """Get Redis pubsub connection"""
        redis = await cls.get_redis()
        return redis.pubsub()

    @classmethod
    async def publish(cls, channel: str, message: str) -> None:
        """Publish message to Redis channel"""
        try:
            redis = await cls.get_redis()
            await redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            raise RedisConnectionError(f"Failed to publish message: {str(e)}")

    @classmethod
    async def subscribe(cls, channel: str) -> None:
        """Subscribe to Redis channel"""
        try:
            pubsub = await cls.get_pubsub()
            await pubsub.subscribe(channel)
        except Exception as e:
            logger.error(f"Failed to subscribe to channel: {str(e)}")
            raise RedisConnectionError(f"Failed to subscribe to channel: {str(e)}")

    @classmethod
    async def get_message(cls, pubsub, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get message from Redis pubsub channel"""
        try:
            return await pubsub.get_message(timeout=timeout)
        except Exception as e:
            logger.error(f"Failed to get message: {str(e)}")
            raise RedisConnectionError(f"Failed to get message: {str(e)}")

    @classmethod
    async def enqueue(cls, queue_name: str, message: str) -> None:
        """Add message to Redis queue"""
        try:
            redis = await cls.get_redis()
            await redis.rpush(queue_name, message)
        except Exception as e:
            logger.error(f"Failed to enqueue message: {str(e)}")
            raise RedisConnectionError(f"Failed to enqueue message: {str(e)}")

    @classmethod
    async def dequeue(cls, queue_name: str, timeout: float = 0) -> Optional[str]:
        """Get message from Redis queue"""
        try:
            redis = await cls.get_redis()
            if timeout > 0:
                result = await redis.blpop(queue_name, timeout=timeout)
                return result[1] if result else None
            else:
                return await redis.lpop(queue_name)
        except Exception as e:
            logger.error(f"Failed to dequeue message: {str(e)}")
            raise RedisConnectionError(f"Failed to dequeue message: {str(e)}")

    @classmethod
    async def invalidate_cache(cls, key_pattern: str = "*") -> None:
        """Invalidate Redis cache entries matching pattern"""
        try:
            redis = await cls.get_redis()
            keys = await redis.keys(key_pattern)
            if keys:
                await redis.delete(*keys)
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {str(e)}")
            raise RedisConnectionError(f"Failed to invalidate cache: {str(e)}")

async def get_redis_client() -> Redis:
    """Get Redis client instance"""
    global _redis_pool
    
    if _redis_pool is None:
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_pool = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=int(os.getenv("REDIS_POOL_SIZE", 20)),
                socket_timeout=int(os.getenv("REDIS_TIMEOUT", 5))
            )
            logger.info("Redis connection pool created")
        except Exception as e:
            logger.error(f"Error creating Redis connection pool: {str(e)}")
            raise

    return _redis_pool

def redis_cache(ttl: int = RedisClient.DEFAULT_TTL):
    """Decorator for caching function results in Redis"""
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            redis = await RedisClient.get_redis()
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
                
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await redis.set(cache_key, json.dumps(result), ex=ttl)
            return result
            
        return wrapper
    return decorator

def clear_redis_cache(pattern: str = "*"):
    """Clear Redis cache entries matching pattern"""
    async def _clear():
        redis = await RedisClient.get_redis()
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    
    asyncio.create_task(_clear())

class RedisCache:
    """Redis cache utility class"""
    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix

    def _get_key(self, key: str) -> str:
        """Get prefixed cache key"""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any:
        """Get value from cache"""
        try:
            redis = await get_redis_client()
            value = await redis.get(self._get_key(key))
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting from cache: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 3600,
        nx: bool = False
    ) -> bool:
        """Set value in cache"""
        try:
            redis = await get_redis_client()
            return await redis.set(
                self._get_key(key),
                json.dumps(value),
                ex=expire,
                nx=nx
            )
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            redis = await get_redis_client()
            return bool(await redis.delete(self._get_key(key)))
        except Exception as e:
            logger.error(f"Error deleting from cache: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            redis = await get_redis_client()
            return bool(await redis.exists(self._get_key(key)))
        except Exception as e:
            logger.error(f"Error checking cache existence: {str(e)}")
            return False

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        try:
            redis = await get_redis_client()
            return bool(await redis.expire(self._get_key(key), seconds))
        except Exception as e:
            logger.error(f"Error setting cache expiration: {str(e)}")
            return False

    async def ttl(self, key: str) -> int:
        """Get key time to live"""
        try:
            redis = await get_redis_client()
            return await redis.ttl(self._get_key(key))
        except Exception as e:
            logger.error(f"Error getting cache TTL: {str(e)}")
            return -2

class RedisList:
    """Redis list utility class"""
    def __init__(self, key: str):
        self.key = key

    async def push(self, value: Any) -> bool:
        """Push value to list"""
        try:
            redis = await get_redis_client()
            return bool(await redis.rpush(self.key, json.dumps(value)))
        except Exception as e:
            logger.error(f"Error pushing to list: {str(e)}")
            return False

    async def pop(self) -> Any:
        """Pop value from list"""
        try:
            redis = await get_redis_client()
            value = await redis.lpop(self.key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error popping from list: {str(e)}")
            return None

    async def length(self) -> int:
        """Get list length"""
        try:
            redis = await get_redis_client()
            return await redis.llen(self.key)
        except Exception as e:
            logger.error(f"Error getting list length: {str(e)}")
            return 0

    async def range(self, start: int = 0, end: int = -1) -> List[Any]:
        """Get range of values from list"""
        try:
            redis = await get_redis_client()
            values = await redis.lrange(self.key, start, end)
            return [json.loads(v) for v in values]
        except Exception as e:
            logger.error(f"Error getting list range: {str(e)}")
            return []

class RedisHash:
    """Redis hash utility class"""
    def __init__(self, key: str):
        self.key = key

    async def get(self, field: str) -> Any:
        """Get hash field value"""
        try:
            redis = await get_redis_client()
            value = await redis.hget(self.key, field)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting hash field: {str(e)}")
            return None

    async def set(self, field: str, value: Any) -> bool:
        """Set hash field value"""
        try:
            redis = await get_redis_client()
            return bool(await redis.hset(self.key, field, json.dumps(value)))
        except Exception as e:
            logger.error(f"Error setting hash field: {str(e)}")
            return False

    async def delete(self, field: str) -> bool:
        """Delete hash field"""
        try:
            redis = await get_redis_client()
            return bool(await redis.hdel(self.key, field))
        except Exception as e:
            logger.error(f"Error deleting hash field: {str(e)}")
            return False

    async def get_all(self) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            redis = await get_redis_client()
            values = await redis.hgetall(self.key)
            return {k: json.loads(v) for k, v in values.items()}
        except Exception as e:
            logger.error(f"Error getting all hash fields: {str(e)}")
            return {}

class RedisLock:
    """Redis distributed lock implementation"""
    def __init__(
        self,
        key: str,
        expire: int = 60,
        retry_delay: float = 0.2,
        retry_times: int = 3
    ):
        self.key = f"lock:{key}"
        self.expire = expire
        self.retry_delay = retry_delay
        self.retry_times = retry_times
        self._redis: Optional[Redis] = None

    async def __aenter__(self) -> bool:
        """Acquire lock"""
        self._redis = await get_redis_client()
        for _ in range(self.retry_times):
            if await self._redis.set(self.key, "1", ex=self.expire, nx=True):
                return True
            await asyncio.sleep(self.retry_delay)
        return False

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release lock"""
        if self._redis:
            await self._redis.delete(self.key)

class RateLimit:
    """Redis-based rate limiting"""
    def __init__(
        self,
        key: str,
        limit: int,
        window: int = 60
    ):
        self.key = f"ratelimit:{key}"
        self.limit = limit
        self.window = window

    async def is_allowed(self) -> bool:
        """Check if action is allowed under rate limit"""
        try:
            redis = await get_redis_client()
            current = await redis.incr(self.key)
            
            if current == 1:
                await redis.expire(self.key, self.window)
            
            return current <= self.limit
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return False

    async def get_remaining(self) -> int:
        """Get remaining allowed actions"""
        try:
            redis = await get_redis_client()
            current = int(await redis.get(self.key) or 0)
            return max(0, self.limit - current)
        except Exception as e:
            logger.error(f"Error getting remaining rate limit: {str(e)}")
            return 0

    async def reset(self) -> bool:
        """Reset rate limit counter"""
        try:
            redis = await get_redis_client()
            return bool(await redis.delete(self.key))
        except Exception as e:
            logger.error(f"Error resetting rate limit: {str(e)}")
            return False
