"""Redis utilities."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from redis.asyncio import Redis, ConnectionPool
from core.config import settings
import asyncio
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None

async def get_redis_pool() -> Optional[ConnectionPool]:
    """Get Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is None:
        try:
            # Ensure REDIS_URL is a string
            redis_url = str(settings.REDIS_URL)
            logger.debug(f"Initializing Redis pool with URL: {redis_url}")
            
            # Check if the URL contains default passwords and remove them
            if "your_redis_password" in redis_url or "your_production_redis_password" in redis_url:
                # Replace with URL without password
                parsed_url = urlparse(redis_url)
                # Remove password from netloc
                netloc_parts = parsed_url.netloc.split("@")
                if len(netloc_parts) > 1:
                    # There's an auth part
                    auth_parts = netloc_parts[0].split(":")
                    if len(auth_parts) > 1:
                        # There's a password
                        netloc = f"{auth_parts[0]}@{netloc_parts[1]}"
                    else:
                        netloc = netloc_parts[1]
                else:
                    netloc = netloc_parts[0]
                
                # Reconstruct URL without password
                redis_url = urlunparse((
                    parsed_url.scheme,
                    netloc,
                    parsed_url.path,
                    parsed_url.params,
                    parsed_url.query,
                    parsed_url.fragment
                ))
                logger.debug(f"Using modified Redis URL without default password: {redis_url}")
            
            # Try to create the pool directly from the URL first
            try:
                _redis_pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                    socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                    socket_connect_timeout=getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                    retry_on_timeout=getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                    health_check_interval=getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                    decode_responses=True
                )
                logger.debug("Redis pool created successfully from URL")
                return _redis_pool
            except Exception as url_error:
                logger.warning(f"Failed to create Redis pool from URL: {str(url_error)}")
                logger.debug("Falling back to manual connection parameters")
            
            # If from_url fails, try with explicit parameters
            # Get the components from settings
            host = settings.REDIS_HOST if hasattr(settings, "REDIS_HOST") else "localhost"
            
            # Ensure port is an integer
            try:
                port = int(settings.REDIS_PORT) if hasattr(settings, "REDIS_PORT") else 6379
            except (ValueError, TypeError):
                logger.warning("Invalid Redis port, using default 6379")
                port = 6379
                
            # Ensure db is an integer
            try:
                db = int(settings.REDIS_DB) if hasattr(settings, "REDIS_DB") else 0
            except (ValueError, TypeError):
                logger.warning("Invalid Redis DB, using default 0")
                db = 0
                
            # Get password if available and not a default value
            password = None
            if (hasattr(settings, "REDIS_PASSWORD") and 
                settings.REDIS_PASSWORD and 
                settings.REDIS_PASSWORD not in ["your_redis_password", "your_production_redis_password"]):
                password = settings.REDIS_PASSWORD
            
            logger.debug(f"Creating Redis pool with explicit parameters - host: {host}, port: {port}, db: {db}")
            
            # Create pool with explicit parameters
            pool_kwargs = {
                "host": host,
                "port": port,
                "db": db,
                "max_connections": getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                "socket_timeout": getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                "socket_connect_timeout": getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                "retry_on_timeout": getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                "health_check_interval": getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                "decode_responses": True
            }
            
            # Add password if present
            if password:
                pool_kwargs["password"] = password
                
            # Create the pool with explicit parameters
            _redis_pool = ConnectionPool(**pool_kwargs)
            logger.debug("Redis pool created successfully with explicit parameters")
            
        except Exception as e:
            logger.error(f"Failed to create Redis connection pool: {str(e)}")
            # Return None instead of raising to allow graceful fallback
            return None
    
    return _redis_pool

async def get_redis_client() -> Optional[Redis]:
    """Get Redis client."""
    global _redis_client, _redis_pool
    
    # If client already exists, return it
    if _redis_client is not None:
        return _redis_client
        
    # If no pool exists, we can't create a client
    if _redis_pool is None:
        try:
            # Try to create the pool directly
            _redis_pool = await get_redis_pool()
        except Exception as e:
            logger.error(f"Failed to create Redis pool: {str(e)}")
            return None
            
    if _redis_pool is None:
        logger.warning("Redis pool is None, cannot create Redis client")
        return None
        
    try:
        # Create the client directly with the pool
        # Avoid using any helper functions to prevent recursion
        _redis_client = Redis(connection_pool=_redis_pool)
        
        # TEMPORARILY DISABLE PING TEST TO AVOID RECURSION
        logger.debug("Redis ping test temporarily disabled")
        return _redis_client
        
        # Test the connection with a direct command - DISABLED
        # try:
        #     # Use a direct command instead of ping() method
        #     command = _redis_client.execute_command("PING")
        #     result = await asyncio.wait_for(command, timeout=2.0)
        #     
        #     if result and result.lower() == "pong":
        #         logger.debug("Redis connection test successful")
        #         return _redis_client
        #     else:
        #         logger.warning(f"Redis ping test returned unexpected result: {result}")
        #         _redis_client = None
        #         return None
        # except asyncio.TimeoutError:
        #     logger.error("Redis ping test timed out")
        #     _redis_client = None
        #     return None
        # except Exception as e:
        #     logger.error(f"Redis ping test failed: {str(e)}")
        #     _redis_client = None
        #     return None
            
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        _redis_client = None
        return None

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
    
    def __init__(self, client=None):
        """Initialize Redis client wrapper.
        
        Args:
            client: Optional Redis client instance. If not provided, 
                   a new client will be initialized.
        """
        self._client = client
        self._pool = None
        self._initialized = False
        
    async def init(self):
        """Initialize Redis client if not already initialized."""
        # If already initialized or client was provided in constructor, return early
        if self._initialized or self._client is not None:
            self._initialized = True
            return
            
        # Don't try to create a new client if there's no global pool
        # This avoids potential recursion
        global _redis_pool
        if _redis_pool is None:
            logger.warning("Global Redis pool is None, cannot create Redis client")
            return
            
        try:
            # Create a direct Redis client without using any helper functions
            # to avoid potential recursion
            from redis.asyncio import Redis
            
            # Create the client directly with the existing pool
            self._client = Redis(connection_pool=_redis_pool)
            
            # Test the connection with a direct command
            try:
                # Use a direct command instead of ping() method to avoid potential recursion
                command = self._client.execute_command("PING")
                result = await asyncio.wait_for(command, timeout=2.0)
                
                if result and result.lower() == "pong":
                    logger.debug("Redis client initialized successfully")
                    self._initialized = True
                else:
                    logger.warning(f"Redis ping test returned unexpected result: {result}")
                    self._client = None
            except asyncio.TimeoutError:
                logger.error("Redis ping test timed out")
                self._client = None
            except Exception as e:
                logger.error(f"Redis ping test failed: {str(e)}")
                self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {str(e)}")
            self._client = None
            
    async def get(self, key: str) -> Any:
        """Get a value from Redis."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot get key")
            return None
        try:
            value = await self._client.get(key)
            if value is None:
                return None
                
            # Try to parse as JSON if it looks like JSON
            if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            elif isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Error getting key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a value in Redis."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot set key")
            return False
        try:
            # Convert dict/list to JSON string
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            if expire:
                return await self._client.setex(key, expire, value)
            return await self._client.set(key, value)
        except Exception as e:
            logger.error(f"Error setting key {key}: {str(e)}")
            return False

    async def setex(self, key: str, time_seconds: int, value: Any) -> bool:
        """Set a value in Redis with expiration."""
        return await self.set(key, value, expire=time_seconds)

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot delete key")
            return False
        try:
            return bool(await self._client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting key {key}: {str(e)}")
            return False

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching a pattern."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot clear pattern")
            return False
        try:
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern)
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            logger.error(f"Error clearing pattern {pattern}: {str(e)}")
            return False

    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment a key by a given amount."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot increment key")
            return 0
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0

    async def ping(self) -> bool:
        """Ping the Redis server."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot ping")
            return False
        try:
            # Use execute_command directly to avoid potential recursion
            result = await self._client.execute_command("PING")
            return result and result.lower() == "pong"
        except Exception as e:
            logger.error(f"Error pinging Redis: {str(e)}")
            return False

    async def close(self) -> None:
        """Close the Redis client."""
        if self._client is not None:
            try:
                await self._client.close()
                self._client = None
            except Exception as e:
                logger.error(f"Error closing Redis client: {str(e)}")

    async def pipeline(self) -> Any:
        """Get a Redis pipeline."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot create pipeline")
            return None
        try:
            return self._client.pipeline()
        except Exception as e:
            logger.error(f"Error creating Redis pipeline: {str(e)}")
            return None

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to a list."""
        if self._client is None:
            logger.warning("Redis client not initialized, cannot push to list")
            return 0
        try:
            return await self._client.lpush(key, *values)
        except Exception as e:
            logger.error(f"Error pushing to list {key}: {str(e)}")
            return 0

class RateLimit:
    """Rate limit implementation using Redis."""
    
    def __init__(self, redis_client: Any, key: str, limit: int, window: int):
        """Initialize rate limit.
        
        Args:
            redis_client: Redis client
            key: Rate limit key
            limit: Maximum number of requests
            window: Time window in seconds
        """
        self._redis = redis_client
        self._key = f"rate_limit:{key}"
        self._limit = limit
        self._window = window
        # Import time here to fix the linter error
        from time import time
        self._time = time
        
    async def is_allowed(self) -> bool:
        """Check if request is allowed."""
        try:
            # Get current count
            count = await self._redis.get(self._key)
            count = int(count) if count else 0
            
            # Check if limit exceeded
            if count >= self._limit:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error getting rate limit counter: {str(e)}")
            return False
            
    async def increment(self) -> None:
        """Increment request counter."""
        try:
            # Get current count
            count = await self._redis.get(self._key)
            count = int(count) if count else 0
            
            # Create pipeline
            pipeline = self._redis.pipeline()
            
            # Increment count
            pipeline.incr(self._key)
            
            # Set expiry if this is the first request
            if count == 0:
                pipeline.expire(self._key, self._window)
            
            await pipeline.execute()
        except Exception as e:
            logger.error(f"Error incrementing rate limit counter: {str(e)}")
            
    async def check_limit(self) -> None:
        """Check rate limit and raise error if exceeded."""
        if not await self.is_allowed():
            # Import RateLimitError here to fix the linter error
            from core.exceptions import RateLimitError
            raise RateLimitError(
                message=f"Rate limit exceeded: {self._limit} requests per {self._window} seconds",
                limit=self._limit,
                reset_at=self._time() + self._window
            )
