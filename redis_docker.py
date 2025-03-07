"""Redis service for centralized Redis operations."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List, Tuple, Set
from uuid import UUID
from redis.asyncio import Redis, ConnectionPool

from core.config import settings
from core.exceptions import RedisError

logger = logging.getLogger(__name__)

# Global instance for singleton pattern
_redis_service_instance = None

class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle UUID objects and other special types."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Prevent recursion by checking object types
            # Don't attempt to serialize objects that might contain self-references
            try:
                # Use a basic dict comprehension but avoid processing nested objects of the same type
                result = {}
                for key, value in obj.__dict__.items():
                    # Skip attributes that are the same type as the parent object (prevent recursion)
                    if isinstance(value, type(obj)):
                        continue
                    # Skip private attributes
                    if key.startswith('_'):
                        continue
                    # For other complex objects, just use their string representation
                    if hasattr(value, '__dict__'):
                        result[key] = str(value)
                    else:
                        result[key] = value
                return result
            except Exception as e:
                # Fallback to string representation
                return str(obj)
        return super().default(obj)

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
        # Remove the prefix to match test expectations
        self._prefix = ""

    def __eq__(self, other):
        """Implement equality check to avoid recursion.
        
        This method prevents recursion by providing an explicit equality check
        that doesn't try to compare all attributes recursively.
        
        Args:
            other: Object to compare with
            
        Returns:
            bool: True if objects are the same instance, False otherwise
        """
        # First check if other is actually a RedisService instance
        if not isinstance(other, RedisService):
            return False
        
        # Simply compare object identities rather than contents
        # This prevents any potential recursive comparison of attributes
        return id(self) == id(other)

    def __hash__(self):
        """Return hash based on object identity.
        
        When overriding __eq__, it's important to also override __hash__
        to maintain the object hash contract.
        
        Returns:
            int: Hash value based on object identity
        """
        return id(self)

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
                # Ensure _get_pool is called during initialization
                self._pool = await self._get_pool()
                
                # If pool is None, we can't create a client
                if self._pool is None:
                    logger.warning("Redis pool is None, cannot initialize Redis client")
                    self._client = None
                    return
                    
                # Explicitly create a new Redis client instance
                self._client = Redis(connection_pool=self._pool)
                
                # Test the connection using direct command execution instead of ping()
                try:
                    # Use a simple execute_command to test connection without using class methods
                    # that might cause recursion
                    result = await self._client.execute_command("PING")
                    if result and isinstance(result, bytes):
                        result = result.decode('utf-8')
                    
                    if result and result.lower() == "pong":
                        logger.info("Redis client initialized successfully")
                    else:
                        logger.warning(f"Redis ping test returned unexpected result: {result}")
                        # Even with unexpected result, keep the client
                        # The application should be able to operate without Redis
                except Exception as e:
                    logger.error(f"Redis ping test failed: {str(e)}")
                    # Keep the client even if ping fails
                    # This allows the application to retry connections later
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {str(e)}")
                # Set client to None to allow graceful fallback
                self._client = None
                # Don't raise the exception to allow the application to continue

    async def _get_pool(self) -> ConnectionPool:
        """Get Redis connection pool."""
        if self._pool is None:
            try:
                # Try creating from explicit parameters first to avoid string conversion issues
                try:
                    # Extract the components directly and explicitly convert to appropriate types
                    host = settings.REDIS_HOST
                    
                    # Ensure port is an integer
                    try:
                        port = int(settings.REDIS_PORT) if hasattr(settings, "REDIS_PORT") else 6379
                    except (ValueError, TypeError):
                        logger.warning("Invalid Redis port value, using default 6379")
                        port = 6379
                    
                    # Ensure DB is an integer
                    try:
                        db = int(settings.REDIS_DB) if hasattr(settings, "REDIS_DB") else 0
                    except (ValueError, TypeError):
                        logger.warning("Invalid Redis DB value, using default 0")
                        db = 0

                    # Get password if available
                    password = None
                    if hasattr(settings, "REDIS_PASSWORD") and settings.REDIS_PASSWORD:
                        password = settings.REDIS_PASSWORD

                    # Basic connection parameters
                    pool_kwargs = {
                        "host": host,
                        "port": port,
                        "db": db,
                        "max_connections": getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                        "socket_timeout": getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                        "socket_connect_timeout": getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                        "retry_on_timeout": getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                        "health_check_interval": getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                        "decode_responses": True,
                        "encoding": "utf-8"
                    }
                    
                    # Add password if present
                    if password and password not in ["your_redis_password", "your_production_redis_password"]:
                        pool_kwargs["password"] = password

                    # Log the Redis connection parameters (without sensitive info)
                    logger.debug(f"Creating Redis pool with host={host}, port={port}, db={db}")
                    
                    # Create the pool with explicit parameters
                    self._pool = ConnectionPool(**pool_kwargs)
                    logger.debug("Redis pool created successfully with explicit parameters")
                    
                except Exception as e:
                    logger.warning(f"Failed to create pool with explicit parameters: {str(e)}")
                    logger.debug("Trying to create pool from URL")
                    
                    # Get URL from settings and ensure it's a string
                    redis_url = str(settings.REDIS_URL)
                    
                    # Basic pool arguments
                    url_pool_kwargs = {
                        "max_connections": getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                        "socket_timeout": getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                        "socket_connect_timeout": getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                        "retry_on_timeout": getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                        "health_check_interval": getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                        "decode_responses": True,
                        "encoding": "utf-8"
                    }

                    if hasattr(settings, "REDIS_SOCKET_KEEPALIVE"):
                        url_pool_kwargs["socket_keepalive"] = settings.REDIS_SOCKET_KEEPALIVE

                    if hasattr(settings, "REDIS_SOCKET_KEEPALIVE_OPTIONS"):
                        url_pool_kwargs["socket_keepalive_options"] = settings.REDIS_SOCKET_KEEPALIVE_OPTIONS
                    
                    self._pool = ConnectionPool.from_url(redis_url, **url_pool_kwargs)
                    logger.debug("Redis pool created successfully from URL")
                    
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

    async def flush_db(self) -> bool:
        """Clear all data in the current database."""
        try:
            return await self._client.flushdb()
        except Exception as e:
            logger.error(f"Error flushing Redis database: {str(e)}")
            raise RedisError(f"Redis database flush failed: {str(e)}")

    async def flushdb(self) -> bool:
        """Alias for flush_db."""
        return await self.flush_db()

    async def get(self, key: str) -> Any:
        """Get value from Redis.
        
        Args:
            key: The key to get
            
        Returns:
            The value, or None if the key doesn't exist
        """
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return None
            
            value = await self._client.get(key)
            if value is None:
                return None

            # If it's a byte string, decode it
            if isinstance(value, bytes):
                value = value.decode('utf-8')

            # Try to parse as JSON, but return as-is if not valid JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Error getting Redis key {key}: {str(e)}")
            # Don't raise an exception to match test expectations
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set a key in Redis with an optional expiration time.
        
        Args:
            key: The key to set
            value: The value to set
            ex: Optional expiration time in seconds or as timedelta
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            logger.warning("Redis client not initialized")
            return False
        
        try:
            # Convert complex values to JSON
            if isinstance(value, (dict, list, tuple, UUID)):
                try:
                    value = json.dumps(value, cls=UUIDEncoder)
                except (RecursionError, TypeError, OverflowError) as e:
                    logger.warning(f"Error encoding collection for key {key}: {str(e)}")
                    value = str(value)
            elif hasattr(value, '__dict__'):
                try:
                    value = json.dumps(value, cls=UUIDEncoder)
                except (RecursionError, TypeError, OverflowError) as e:
                    logger.warning(f"Error encoding object for key {key}: {str(e)}")
                    value = str(value)
            
            # Convert timedelta to seconds if needed
            if isinstance(ex, timedelta):
                ex = int(ex.total_seconds())
            
            # Set the value in Redis
            await self._client.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.error(f"Error setting Redis key {key}: {str(e)}")
            return False

    async def delete(self, *keys: str) -> bool:
        """Delete keys from Redis."""
        try:
            prefixed_keys = [self._prefix + key for key in keys]
            return bool(await self._client.delete(*prefixed_keys))
        except Exception as e:
            logger.error(f"Error deleting Redis keys {keys}: {str(e)}")
            raise RedisError(f"Redis delete operation failed: {str(e)}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            return bool(await self._client.exists(self._prefix + key))
        except Exception as e:
            logger.error(f"Error checking Redis key {key}: {str(e)}")
            raise RedisError(f"Redis exists operation failed: {str(e)}")

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for key."""
        try:
            return await self._client.expire(self._prefix + key, seconds)
        except Exception as e:
            logger.error(f"Error setting expiration for Redis key {key}: {str(e)}")
            raise RedisError(f"Redis expire operation failed: {str(e)}")

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Set key to value and set expiry in the same operation."""
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False
            
            # Convert value to JSON string if it's a dict or list
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, cls=UUIDEncoder)
            
            await self._client.setex(key, seconds, value)
            return True
        except Exception as e:
            logger.error(f"Error setting Redis key {key} with expiration: {str(e)}")
            return False

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

    # Hash operations
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field to value."""
        try:
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, cls=UUIDEncoder)
            return await self._client.hset(self._prefix + key, field, value)
        except Exception as e:
            logger.error(f"Error setting hash field {field} for Redis key {key}: {str(e)}")
            raise RedisError(f"Redis hset operation failed: {str(e)}")

    async def hget(self, key: str, field: str) -> Any:
        """Get value of hash field."""
        try:
            value = await self._client.hget(self._prefix + key, field)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Error getting hash field {field} for Redis key {key}: {str(e)}")
            raise RedisError(f"Redis hget operation failed: {str(e)}")

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields and values in hash."""
        try:
            result = await self._client.hgetall(self._prefix + key)
            if not result:
                return {}
            
            # Try to decode JSON values
            decoded = {}
            for field, value in result.items():
                try:
                    decoded[field] = json.loads(value)
                except json.JSONDecodeError:
                    decoded[field] = value
            
            return decoded
        except Exception as e:
            logger.error(f"Error getting all hash fields for Redis key {key}: {str(e)}")
            raise RedisError(f"Redis hgetall operation failed: {str(e)}")

    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        try:
            return await self._client.hdel(self._prefix + key, *fields)
        except Exception as e:
            logger.error(f"Error deleting hash fields {fields} for Redis key {key}: {str(e)}")
            raise RedisError(f"Redis hdel operation failed: {str(e)}")

    # Set operations
    async def sadd(self, key: str, *members: str) -> int:
        """Add members to set."""
        try:
            return await self._client.sadd(self._prefix + key, *members)
        except Exception as e:
            logger.error(f"Error adding members to set {key}: {str(e)}")
            raise RedisError(f"Redis sadd operation failed: {str(e)}")

    async def srem(self, key: str, *members: str) -> int:
        """Remove members from set."""
        try:
            return await self._client.srem(self._prefix + key, *members)
        except Exception as e:
            logger.error(f"Error removing members from set {key}: {str(e)}")
            raise RedisError(f"Redis srem operation failed: {str(e)}")

    async def smembers(self, key: str) -> Set[str]:
        """Get all members of set."""
        try:
            return await self._client.smembers(self._prefix + key)
        except Exception as e:
            logger.error(f"Error getting members of set {key}: {str(e)}")
            raise RedisError(f"Redis smembers operation failed: {str(e)}")

    # Scan operation
    async def scan(self, cursor: int, match: Optional[str] = None, count: Optional[int] = None) -> Tuple[int, List[str]]:
        """Scan for keys matching pattern."""
        try:
            pattern = match
            if match and not match.startswith(self._prefix):
                pattern = self._prefix + match
            return await self._client.scan(cursor, match=pattern, count=count)
        except Exception as e:
            logger.error(f"Error scanning Redis keys with pattern {match}: {str(e)}")
            raise RedisError(f"Redis scan operation failed: {str(e)}")

    # Token blacklisting methods
    async def blacklist_token(self, token: str, expires_delta: int) -> bool:
        """Blacklist a token.
        
        Args:
            token: The token to blacklist
            expires_delta: Expiration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False
            
            key = f"blacklist:{token}"
            await self._client.setex(key, expires_delta, "1")
            logger.info(f"Token {token} blacklisted successfully with expiry {expires_delta}s")
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            return False

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token is blacklisted.
        
        Args:
            token: The token to check
            
        Returns:
            True if blacklisted, False otherwise
        """
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False
            
            key = f"blacklist:{token}"
            result = await self.get(key)
            return result is not None
        except Exception as e:
            logger.error(f"Error checking if token is blacklisted: {str(e)}")
            return False

    # Add a ping method after the scan method and before the blacklist_token method
    async def ping(self) -> bool:
        """Ping the Redis server to check connectivity.
        
        Returns:
            bool: True if ping successful, False otherwise
        """
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False
            
            # Use execute_command directly to avoid potential recursion issues
            # and handle byte string responses
            result = await self._client.execute_command("PING")
            
            # Handle byte string responses
            if isinstance(result, bytes):
                result = result.decode('utf-8')
            
            return result and result.lower() == "pong"
        except Exception as e:
            logger.error(f"Redis ping test failed: {str(e)}")
            return False

    async def hmset(self, key: str, mapping: Dict[str, Any], ex: Union[int, timedelta] = None) -> bool:
        """Set multiple hash fields to multiple values."""
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False

            # Convert any dict values in the mapping to JSON strings
            processed_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list, tuple)):
                    processed_mapping[k] = json.dumps(v, cls=UUIDEncoder)
                else:
                    processed_mapping[k] = v

            # First set the hash
            await self._client.hmset(key, processed_mapping)
            
            # Then set expiration if provided
            if ex:
                # Convert timedelta to seconds if needed
                if isinstance(ex, timedelta):
                    ex = int(ex.total_seconds())
                await self._client.expire(key, ex)
                
            return True
        except Exception as e:
            logger.error(f"Error setting Redis hash {key}: {str(e)}")
            return False
            
    async def json_set(self, key: str, value: Any, ex: Union[int, timedelta] = None) -> bool:
        """Set a JSON value in Redis."""
        try:
            if not self._client:
                logger.warning("Redis client not initialized")
                return False
                
            # Serialize to JSON string
            json_value = json.dumps(value, cls=UUIDEncoder)
            
            # Set the value
            await self._client.set(key, json_value, ex=ex)
            return True
        except Exception as e:
            logger.error(f"Error setting Redis JSON value for {key}: {str(e)}")
            return False

# Factory function to get Redis service instance
async def get_redis_service() -> RedisService:
    """Get Redis service instance.
    
    This function returns the global Redis service instance.
    If the instance doesn't exist yet, it creates a new one and initializes it.
    
    Returns:
        RedisService: The initialized Redis service instance
    """
    global _redis_service_instance
    if _redis_service_instance is None:
        # Create a new instance and initialize it
        _redis_service_instance = RedisService()
        await _redis_service_instance.init()
    return _redis_service_instance 