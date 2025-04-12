"""Redis service for centralized Redis operations."""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, Union, List, Tuple, Set, TypeVar, Callable, cast
from uuid import UUID
from redis.asyncio import Redis, ConnectionPool
from decimal import Decimal
import urllib.parse
import asyncio
from contextvars import ContextVar
import inspect
import traceback
import time
from enum import Enum

from core.config import settings
from core.exceptions import RedisError

logger = logging.getLogger(__name__)

# Global variables for connection management
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None
_initialized: bool = False

# Import the built-in set type with a different name to avoid conflicts
from builtins import set as builtin_set

# Keep track of objects being encoded to prevent recursion
_encoding_context = ContextVar("encoding_context", default=set())
_max_encoding_depth = ContextVar("max_encoding_depth", default=0)

class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUIDs, datetimes, and other complex types.
    
    This encoder will convert:
    - UUID objects to strings
    - Decimal objects to floats
    - Datetime objects to ISO format strings
    - Set objects to lists
    - SQLAlchemy models to simplified dictionaries
    
    Additionally, it tracks serialization depth to prevent infinite recursion.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize context vars if they're not already set
        try:
            _encoding_context.get()
        except LookupError:
            _encoding_context.set(set())
        
        try:
            _max_encoding_depth.get()
        except LookupError:
            _max_encoding_depth.set(0)
    
    def default(self, obj):
        # Check recursion depth
        depth = _max_encoding_depth.get()
        _max_encoding_depth.set(depth + 1)
        
        # Prevent excessive recursion - reduced max depth from 10 to 4 (more aggressive)
        if depth > 4:
            _max_encoding_depth.set(depth)  # Reset depth
            return f"<Object at depth {depth} - recursion limit>"
            
        # Track objects by id to prevent circular references
        obj_id = id(obj)
        encoding_context = _encoding_context.get()
        
        # If we've seen this object before, don't serialize it again
        if obj_id in encoding_context:
            _max_encoding_depth.set(depth)  # Reset depth
            return f"<Circular reference to {type(obj).__name__}>"
            
        # Add current object to context
        new_context = encoding_context.copy()
        new_context.add(obj_id)
        token = _encoding_context.set(new_context)
        
        try:
            # Handle specific types directly
            if isinstance(obj, UUID):
                result = str(obj)
            elif isinstance(obj, Decimal):
                result = float(obj)
            elif isinstance(obj, (datetime, date)):
                result = obj.isoformat()
            elif isinstance(obj, (set, frozenset)):
                result = list(obj)
            # Handle common types that might cause recursion issues
            elif isinstance(obj, dict):
                # For very deep objects, use a simplified representation
                if depth > 2:
                    # Just return a summary for deep dictionaries
                    result = f"<Dict with {len(obj)} items>"
                else:
                    # Process each key-value pair separately with limited entries
                    result = {}
                    for i, (k, v) in enumerate(obj.items()):
                        # Limit entries to prevent huge dictionaries
                        if i >= 25:  # More aggressive limit (was 50)
                            result['...'] = f"<{len(obj) - 25} more items>"
                            break
                        
                        # Skip callable items, private attributes, and complex nested structures
                        if not callable(v) and not (isinstance(k, str) and k.startswith('_')):
                            try:
                                # Convert key to string if it's not already
                                k_str = str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k
                                # For deeper levels, use simpler representations of complex values
                                if depth > 1 and hasattr(v, '__dict__'):
                                    result[k_str] = f"<{type(v).__name__} object>"
                                else:
                                    result[k_str] = v
                            except Exception:
                                # If we can't convert the key or value, skip this item
                                continue
            elif inspect.isasyncgen(obj):
                # Handle async generators
                result = "<async generator object>"
            elif hasattr(obj, '__dict__') and not isinstance(obj, type):
                # For model objects at deep levels, use a simple representation
                if depth > 2:
                    result = f"<{type(obj).__name__} object>"
                else:
                    # Convert to dict, skipping private and callable attributes
                    try:
                        result = {}
                        items = list(obj.__dict__.items())[:25]  # More aggressive limit (was 50)
                        for k, v in items:
                            if not k.startswith('_') and not callable(v):
                                try:
                                    # For deeper levels, use simpler representations
                                    if depth > 1 and hasattr(v, '__dict__'):
                                        result[k] = f"<{type(v).__name__} object>"
                                    else:
                                        result[k] = v
                                except Exception:
                                    # Skip attributes that can't be processed
                                    continue
                    except Exception:
                        # If accessing __dict__ fails, use a simple representation
                        result = f"<{type(obj).__name__} object>"
            elif hasattr(obj, '__slots__'):
                # For slot-based objects at deep levels, use a simple representation
                if depth > 2:
                    result = f"<{type(obj).__name__} object with slots>"
                else:
                    # Handle objects with __slots__ instead of __dict__
                    try:
                        result = {}
                        slots = list(obj.__slots__)[:25]  # More aggressive limit
                        for slot in slots:
                            if not slot.startswith('_'):
                                try:
                                    value = getattr(obj, slot, None)
                                    if not callable(value):
                                        # Simplify nested objects
                                        if depth > 1 and hasattr(value, '__dict__'):
                                            result[slot] = f"<{type(value).__name__} object>"
                                        else:
                                            result[slot] = value
                                except Exception:
                                    # Skip attributes that can't be processed
                                    continue
                    except Exception:
                        result = f"<{type(obj).__name__} object with slots>"
            elif hasattr(obj, '_asdict') and callable(getattr(obj, '_asdict', None)):
                # Handle namedtuples and similar objects
                try:
                    result = obj._asdict()
                except Exception:
                    result = f"<{type(obj).__name__} namedtuple-like object>"
            elif inspect.iscoroutine(obj) or inspect.isawaitable(obj):
                # Handle coroutines and awaitable objects
                result = f"<{type(obj).__name__} coroutine>"
            elif inspect.isgenerator(obj) or inspect.isgeneratorfunction(obj):
                # Handle generator objects
                result = f"<{type(obj).__name__} generator>"
            else:
                # Try default serialization
                try:
                    result = super().default(obj)
                except TypeError:
                    # If that fails, try to represent as a string
                    try:
                        result = str(obj)
                    except Exception:
                        # Last resort - just use the type name
                        result = f"<{type(obj).__name__} unserializable object>"
                
        except Exception as e:
            # Catch any other exceptions during serialization
            logger.warning(f"Error serializing object of type {type(obj).__name__}: {str(e)}")
            result = f"<Error serializing {type(obj).__name__}: {str(e)[:50]}>"
            
        finally:
            # Reset the encoding context
            _encoding_context.reset(token)
            # Reset depth
            _max_encoding_depth.set(depth)
            
        return result

def _encode_complex_type(obj):
    """Helper function to encode complex types for JSON serialization.
    
    This is used as the 'default' parameter for json.dumps() to handle types
    that aren't natively supported by the JSON encoder.
    
    Args:
        obj: The object to encode
        
    Returns:
        A JSON serializable version of the object
    """
    # Handle UUID
    if isinstance(obj, UUID):
        return str(obj)
        
    # Handle datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
        
    # Handle Decimal
    if isinstance(obj, Decimal):
        return float(obj)
        
    # Handle Enum
    if isinstance(obj, Enum):
        return obj.value
        
    # Handle sets
    if isinstance(obj, (set, frozenset)):
        return list(obj)
        
    # Handle Pydantic models
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
        
    # Handle objects with __dict__
    if hasattr(obj, "__dict__"):
        # Filter out private attributes and callables
        return {k: v for k, v in obj.__dict__.items() 
                if not k.startswith("_") and not callable(v)}
                
    # Default fallback
    return str(obj)

# RedisService class - delegates to functional API
class RedisService:
    """Redis service for centralized Redis operations.
    
    This class provides backward compatibility with existing code.
    All methods delegate to the functional API to avoid recursion issues.
    """
    
    # Class variable for singleton pattern
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one Redis service instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize attributes only once
            cls._instance._pool = None
            cls._instance._client = None
            cls._instance._initialized = False
            cls._instance._prefix = ""
        return cls._instance
    
    # Override equality and hash methods to avoid recursion
    def __eq__(self, other):
        """Simple identity comparison to prevent recursion."""
        return self is other
    
    def __hash__(self):
        """Simple identity-based hash to match __eq__."""
        return id(self)
    
    @classmethod
    async def get_instance(cls) -> 'RedisService':
        """Get Redis service instance."""
        if cls._instance is None:
            cls._instance = cls()
        
        # Initialize if not already initialized
        if not cls._instance._initialized:
            await cls._instance.init()
        
        return cls._instance
    
    async def init(self, client: Optional[Redis] = None) -> None:
        """Initialize Redis client."""
        if self._initialized and self._client is not None:
            return
            
        if client:
            self._client = client
            self._initialized = True
            return
            
        # Use the functional API to get a client
        self._client = await get_redis_client()
        self._pool = _redis_pool
        self._initialized = True
    
    async def close(self) -> None:
        """Close Redis connections."""
        # Call the functional API to close connections
        await close_redis()
        
        # Reset instance state
        self._client = None
        self._pool = None
        self._initialized = False
        
        # Reset singleton instance
        RedisService._instance = None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from Redis.
        
        Args:
            key: The key to get
            default: The default value to return if the key doesn't exist
            
        Returns:
            The value if it exists, otherwise the default value
        """
        try:
            if self._client is None:
                await self.init()
            
            value = await self._client.get(key)
            if value is None:
                return default
            
            # Try to deserialize from JSON if it looks like JSON
            if isinstance(value, bytes):
                value = value.decode('utf-8')
                
            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                try:
                    return json.loads(value)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSONDecodeError for key {key}: {str(e)}")
                    # If not valid JSON, return as is
                    return value
                except Exception as e:
                    logger.warning(f"Error parsing JSON for key {key}: {str(e)}")
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Failed to get key {key} from Redis: {str(e)}")
            return default
    
    async def set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False, xx: bool = False):
        """Set a key-value pair in Redis.
        
        Args:
            key: Redis key
            value: Value to store (will be serialized)
            ex: Expiration time in seconds
            nx: Only set if key does not exist
            xx: Only set if key exists
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get Redis client
            redis = await get_redis_client()
            if not redis:
                return False
                
            # Prepare value for storage
            if value is None:
                # Store None as an empty string with special marker
                redis_value = "__null__"
            else:
                try:
                    # Simplify complex objects for serialization
                    simplified = await self._simplify_object(value, max_depth=5, current_depth=0)
                    
                    # Convert to JSON
                    redis_value = json.dumps(simplified, cls=UUIDEncoder)
                except Exception as e:
                    logger.warning(f"Error serializing value for Redis: {e}")
                    # Fallback to string representation with error info
                    redis_value = json.dumps({
                        "__error__": f"Serialization error: {str(e)}",
                        "__type__": str(type(value)),
                        "__str__": str(value)[:1000]  # Limit length
                    })
                    
            # Set with appropriate options
            if ex is not None:
                if nx:
                    return await redis.set(key, redis_value, ex=ex, nx=True)
                elif xx:
                    return await redis.set(key, redis_value, ex=ex, xx=True)
                else:
                    return await redis.set(key, redis_value, ex=ex)
            else:
                if nx:
                    return await redis.set(key, redis_value, nx=True)
                elif xx:
                    return await redis.set(key, redis_value, xx=True)
                else:
                    return await redis.set(key, redis_value)
                    
        except Exception as e:
            logger.warning(f"Error setting value in Redis: {e}")
            return False
    
    async def _simplify_object(self, obj: Any, max_depth: int = 3, current_depth: int = 0) -> Any:
        """Recursively simplify a complex object for serialization.
        
        This handles:
        - Nested dicts/lists
        - Pydantic models
        - UUID objects
        - Datetime objects
        - Enum values
        - Custom objects with __dict__
        
        Args:
            obj: Object to simplify
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            Simplified value suitable for JSON serialization
        """
        # Prevent potential infinite recursion by checking recursion depth
        if current_depth >= max_depth:
            # Return a string representation for deeply nested objects
            if isinstance(obj, (dict, list)):
                return f"{type(obj).__name__}[truncated at depth {max_depth}]"
            return str(obj)
            
        # Handle None
        if obj is None:
            return None
            
        # Handle basic types that can be serialized directly
        if isinstance(obj, (str, int, float, bool)):
            return obj
            
        # Handle UUID
        if isinstance(obj, UUID):
            return str(obj)
            
        # Handle datetime
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
            
        # Handle Pydantic models
        if hasattr(obj, "model_dump"):
            try:
                model_data = obj.model_dump()
                # Use iterative approach for dictionaries
                return await self._simplify_object(model_data, max_depth, current_depth + 1)
            except Exception as e:
                logger.error(f"Error dumping Pydantic model: {e}")
                return str(obj)
                
        if hasattr(obj, "dict") and callable(obj.dict):
            try:
                dict_data = obj.dict()
                return await self._simplify_object(dict_data, max_depth, current_depth + 1)
            except Exception as e:
                logger.error(f"Error converting object to dict: {e}")
                return str(obj)
            
        # Handle enums
        if isinstance(obj, Enum):
            return obj.value
            
        # Handle dictionaries - avoid recursive calls for each key-value pair 
        # by using a simplified approach for deeper levels
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Skip private attributes
                if isinstance(key, str) and key.startswith('_'):
                    continue
                    
                # Convert key to string if it's not a basic type
                if not isinstance(key, (str, int, float, bool)):
                    simple_key = str(key)
                else:
                    simple_key = key
                    
                # For deeper levels, use simplified serialization
                if current_depth + 1 >= max_depth:
                    result[simple_key] = str(value)
                else:
                    try:
                        result[simple_key] = await self._simplify_object(value, max_depth, current_depth + 1)
                    except Exception as e:
                        # If we can't simplify the value, store an error message
                        result[simple_key] = f"Error: {str(e)}"
            return result
            
        # Handle lists with similar approach to dictionaries
        if isinstance(obj, (list, set, tuple)):
            result = []
            for item in obj:
                if current_depth + 1 >= max_depth:
                    result.append(str(item))
                else:
                    try:
                        result.append(await self._simplify_object(item, max_depth, current_depth + 1))
                    except Exception as e:
                        result.append(f"Error: {str(e)}")
            return result
            
        # Handle objects with a __dict__ attribute
        if hasattr(obj, "__dict__"):
            try:
                obj_dict = obj.__dict__
                # Skip if the __dict__ is the same object (self-reference)
                if id(obj_dict) == id(obj):
                    return str(obj)
                return await self._simplify_object(obj_dict, max_depth, current_depth + 1)
            except Exception as e:
                logger.error(f"Error accessing __dict__: {e}")
                return str(obj)
            
        # If all else fails, convert to string
        return str(obj)
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key was deleted, False otherwise
        """
        try:
            if self._client is None:
                await self.init()
            
            result = await self._client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete key {key} from Redis: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        return await exists(key)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        return await expire(key, seconds)
    
    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Set key with expiration."""
        return await self.set(key, value, ex=seconds)
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field."""
        return await hset(key, field, value)
    
    async def hget(self, key: str, field: str) -> Any:
        """Get hash field."""
        return await hget(key, field)
    
    async def hmset(self, key: str, mapping: Dict[str, Any], ex: Union[int, timedelta] = None) -> bool:
        """Set multiple hash fields."""
        return await hmset(key, mapping, ex)
    
    async def json_set(self, key: str, value: Any, ex: Union[int, timedelta] = None) -> bool:
        """Set JSON value."""
        return await json_set(key, value, ex)
    
    async def sadd(self, key: str, *members: Any) -> int:
        """Add members to a set."""
        return await sadd(key, *members)
    
    async def srem(self, key: str, *members: Any) -> int:
        """Remove members from a set."""
        return await srem(key, *members)
    
    async def smembers(self, key: str) -> Set[Any]:
        """Get all members of a set."""
        return await smembers(key)
    
    async def sismember(self, key: str, member: Any) -> bool:
        """Check if a member exists in a set."""
        return await sismember(key, member)
    
    async def ping(self) -> bool:
        """Check Redis connection with a direct ping command.
        
        This is a standalone function that avoids using other Redis methods
        to prevent recursion issues.
        
        Returns:
            bool: True if Redis is connected and responding, False otherwise
        """
        # Call the module-level ping function to avoid recursion
        result = await ping()
        return result
    
    async def flushdb(self) -> bool:
        """Flush database."""
        client = await get_redis_client()
        if client is None:
            return False
        try:
            return await client.flushdb()
        except Exception as e:
            logger.error(f"Error flushing Redis database: {str(e)}")
            return False
    
    async def flush_db(self) -> bool:
        """Alias for flushdb."""
        return await self.flushdb()
    
    async def blacklist_token(self, token: str, expires_delta: int) -> bool:
        """Blacklist a token."""
        client = await get_redis_client()
        if client is None:
            return False
        try:
            key = f"blacklist:{token}"
            await client.setex(key, expires_delta, "1")
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            return False
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        key = f"blacklist:{token}"
        return await exists(key)

    async def pipeline(self):
        """Get a Redis pipeline for batch operations.
        
        Returns:
            A Redis pipeline
        """
        try:
            if self._client is None:
                await self.init()
            
            return self._client.pipeline()
        except Exception as e:
            logger.error(f"Failed to create Redis pipeline: {str(e)}")
            # Return a mock pipeline that does nothing
            return MockRedisPipeline()

async def get_redis_pool() -> Optional[ConnectionPool]:
    """Get Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is not None:
        return _redis_pool
        
    try:
        # Try creating from explicit parameters first
        try:
            # Extract components from settings
            host = getattr(settings, "REDIS_HOST", "redis")  # Use "redis" as default
            
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
                if password in ["your_production_redis_password"]:
                    password = None
                # We're keeping "your_redis_password" as valid since it's used in Docker compose

            # Set up connection parameters
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
            if password is not None:
                pool_kwargs["password"] = password

            # Log connection parameters (without sensitive data)
            logger.debug(f"Creating Redis pool with host={host}, db={db}")
            
            # Create the pool
            _redis_pool = ConnectionPool(**pool_kwargs)
            logger.debug("Redis pool created successfully with explicit parameters")
            
        except Exception as e:
            logger.warning(f"Failed to create pool with explicit parameters: {str(e)}")
            logger.debug("Trying to create pool from URL")
            
            # Get URL from settings
            redis_url = str(settings.REDIS_URL)
            
            # Create the pool from URL
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
            
    except Exception as e:
        logger.error(f"Failed to create Redis connection pool: {str(e)}")
        _redis_pool = None
        
    return _redis_pool

async def get_redis_client() -> Optional[Redis]:
    """Get Redis client.
    
    Follows Redis best practices for connection management:
    - Uses connection pooling
    - Handles authentication properly
    - Implements health checks
    - Properly configures connection timeouts
    - Avoids recursion issues with initialization
    """
    global _redis_client, _redis_pool, _initialized
    
    # Return existing client if already initialized, even if it's None
    if _initialized:
        logger.debug("Redis client already initialized - returning existing client")
        return _redis_client
    
    # Add a flag to prevent recursion
    if getattr(get_redis_client, "_in_progress", False):
        logger.warning("Detected potential recursion in Redis initialization, returning None to break cycle")
        return None
        
    # Set in-progress flag
    setattr(get_redis_client, "_in_progress", True)
    
    try:
        # Get Redis configuration from settings
        redis_host = getattr(settings, "REDIS_HOST", "redis")
        redis_port = getattr(settings, "REDIS_PORT", 6379)
        redis_db = getattr(settings, "REDIS_DB", 0)
        
        # Force use of 'redis' host when running in Docker
        if settings.APP_ENVIRONMENT != "local" and redis_host == "localhost":
            logger.warning("Overriding 'localhost' to 'redis' for Docker compatibility")
            redis_host = "redis"
            
        logger.info(f"Redis host being used: {redis_host}")
        
        # Handle authentication properly
        password = getattr(settings, "REDIS_PASSWORD", None)
        if password in ["your_production_redis_password", None, ""]:
            # Use None for password if it's not set or is a placeholder
            # We're keeping "your_redis_password" as valid since it's used in Docker compose
            password = None
            
        # Only create a new pool & client if we don't have one yet or if the settings have changed
        if _redis_pool is None:
            logger.info(f"Creating new Redis connection pool to {redis_host}:{redis_port}/{redis_db}")
            
            # Prepare connection options
            socket_timeout = getattr(settings, "REDIS_SOCKET_TIMEOUT", 5)
            socket_connect_timeout = getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5)
            socket_keepalive = getattr(settings, "REDIS_SOCKET_KEEPALIVE", True)
            
            # Create pool with proper security and performance settings
            _redis_pool = ConnectionPool(
                host=redis_host,
                port=int(redis_port),
                db=int(redis_db),
                password=password,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                socket_keepalive=socket_keepalive,
                health_check_interval=30,
                retry_on_timeout=True,
                max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 10)),
                retry_on_error=[RedisError]
            )
            
            # Create Redis client with connection pool
            _redis_client = Redis(connection_pool=_redis_pool, decode_responses=True)
            
            # Test the connection
            try:
                logger.info("Testing Redis connection")
                async_redis = _redis_client
                # Don't use ping() here directly as it would cause another call to this function
                pong = await async_redis.execute_command("PING")
                if pong:
                    logger.info("Successfully connected to Redis")
                else:
                    logger.error("Failed to connect to Redis: PING returned unexpected response")
                    _redis_client = None
            except RedisError as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                _redis_client = None
                _redis_pool = None
        
        # Mark as initialized to prevent further initialization attempts
        # Even if initialization failed, we don't want to keep trying
        _initialized = True
        
        return _redis_client
    except Exception as e:
        logger.error(f"Error initializing Redis client: {str(e)}")
        return None
    finally:
        # Always clear the in-progress flag
        setattr(get_redis_client, "_in_progress", False)

async def close_redis() -> None:
    """Close Redis connections."""
    global _redis_client, _redis_pool, _initialized
    
    # Close client
    if _redis_client is not None:
        try:
            import asyncio
            close_task = _redis_client.close()
            await asyncio.wait_for(close_task, timeout=2.0)
            logger.debug("Redis client closed successfully")
        except asyncio.TimeoutError:
            logger.error("Redis client close operation timed out")
        except Exception as e:
            logger.error(f"Error closing Redis client: {str(e)}")
            
    # Close pool
    if _redis_pool is not None:
        try:
            import asyncio
            if hasattr(_redis_pool, "disconnect"):
                disconnect_task = _redis_pool.disconnect()
                await asyncio.wait_for(disconnect_task, timeout=2.0)
                logger.debug("Redis pool disconnected successfully")
        except asyncio.TimeoutError:
            logger.error("Redis pool disconnect operation timed out")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {str(e)}")
            
    # Reset variables
    _redis_client = None
    _redis_pool = None
    _initialized = False

# Redis operations

async def ping() -> bool:
    """Check Redis connection with a direct ping command.
    
    This is a standalone function that avoids using other Redis methods
    to prevent recursion issues.
    
    Returns:
        bool: True if Redis is connected and responding, False otherwise
    """
    global _redis_client
    
    # If client doesn't exist, can't ping
    if _redis_client is None:
        logger.warning("Cannot ping Redis: client not initialized")
        return False
        
    try:
        import asyncio
        
        # Use a simple raw command execution to avoid any potential recursion
        # Directly access the underlying connection pool to avoid method calls
        # that might trigger other functions
        ping_command = _redis_client.execute_command("PING")
        ping_result = await asyncio.wait_for(ping_command, timeout=1.0)
        
        # Check result
        if isinstance(ping_result, bytes):
            ping_result = ping_result.decode('utf-8')
            
        if ping_result == "PONG":
            logger.debug("Redis ping successful")
            return True
        else:
            logger.warning(f"Redis ping returned unexpected response: {ping_result}")
            return False
            
    except asyncio.TimeoutError:
        logger.error("Redis ping timed out")
        return False
    except Exception as e:
        logger.error(f"Redis ping failed: {str(e)}")
        return False

async def exists(key: str) -> bool:
    """Check if key exists in Redis."""
    # Add a recursion guard
    if getattr(exists, "_in_exists_call", False):
        logger.warning("Recursion detected in Redis exists() call")
        return False
        
    try:
        exists._in_exists_call = True
        client = await get_redis_client()
        
        if client is None:
            return False
            
        try:
            return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Error checking if Redis key {key} exists: {str(e)}")
            return False
    finally:
        exists._in_exists_call = False

async def expire(key: str, seconds: int) -> bool:
    """Set expiration on key."""
    client = await get_redis_client()
    
    if client is None:
        return False
        
    try:
        return bool(await client.expire(key, seconds))
    except Exception as e:
        logger.error(f"Error setting expiration on Redis key {key}: {str(e)}")
        return False

async def hset(key: str, field: str, value: Any) -> bool:
    """Set hash field in Redis."""
    client = await get_redis_client()
    
    if client is None:
        return False
        
    try:
        # Convert complex objects to JSON
        if not isinstance(value, (str, int, float, bool, type(None))):
            value = json.dumps(value, cls=UUIDEncoder)
            
        result = await client.hset(key, field, value)
        return result >= 0
    except Exception as e:
        logger.error(f"Error setting Redis hash field {key}.{field}: {str(e)}")
        return False

async def hget(key: str, field: str) -> Any:
    """Get hash field from Redis."""
    client = await get_redis_client()
    
    if client is None:
        return None
        
    try:
        return await client.hget(key, field)
    except Exception as e:
        logger.error(f"Error getting Redis hash field {key}.{field}: {str(e)}")
        return None

async def hmset(key: str, mapping: Dict[str, Any], ex: Union[int, timedelta] = None) -> bool:
    """Set multiple hash fields in Redis."""
    client = await get_redis_client()
    
    if client is None:
        return False
        
    try:
        # Process mapping for non-primitive values
        processed = {}
        for k, v in mapping.items():
            if isinstance(v, (dict, list, tuple)):
                processed[k] = json.dumps(v, cls=UUIDEncoder)
            else:
                processed[k] = v
                
        # Execute command
        result = await client.hset(key, mapping=processed)
        
        # Set expiration if provided
        if ex is not None and result >= 0:
            seconds = ex if isinstance(ex, int) else int(ex.total_seconds())
            await client.expire(key, seconds)
            
        return result >= 0
    except Exception as e:
        logger.error(f"Error setting multiple Redis hash fields for {key}: {str(e)}")
        return False

async def json_set(key: str, value: Any, ex: Union[int, timedelta] = None) -> bool:
    """Set a JSON value in Redis.
    
    Args:
        key: Redis key
        value: Value to store (will be serialized to JSON)
        ex: Expiration time in seconds or timedelta
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert timedelta to seconds if needed
        if isinstance(ex, timedelta):
            ex = int(ex.total_seconds())
            
        # Get Redis client
        redis = await get_redis_client()
        if not redis:
            return False
            
        # Prepare value for storage
        if value is None:
            # Store None as a special marker
            redis_value = "__null__"
        else:
            try:
                # Serialize value with safety limits
                redis_value = json.dumps(value, cls=UUIDEncoder, default=_encode_complex_type)
            except (RecursionError, TypeError, ValueError, json.JSONDecodeError) as e:
                logger.warning(f"Error serializing complex value for Redis: {e}")
                # Fall back to simple string representation
                redis_value = json.dumps({
                    "__error__": f"Serialization error: {str(e)}",
                    "__type__": str(type(value)),
                    "__str__": str(value)[:1000]  # Limit string length
                })
                
        # Set the value with expiration if provided
        if ex is not None:
            return await redis.set(key, redis_value, ex=ex)
        else:
            return await redis.set(key, redis_value)
            
    except Exception as e:
        logger.warning(f"Error setting JSON in Redis: {e}")
        return False

async def sadd(key: str, *members: Any) -> int:
    """Add members to a set.
    
    Args:
        key: Set key
        *members: One or more members to add to the set
        
    Returns:
        int: Number of members added to the set (not including existing members)
    """
    client = await get_redis_client()
    if client is None:
        logger.warning(f"Failed to add members to set {key}: Redis client not available")
        return 0
    
    try:
        serialized_members = [json.dumps(m, cls=UUIDEncoder) if not isinstance(m, (str, int, float, bool)) else m for m in members]
        result = await client.sadd(key, *serialized_members)
        return result
    except Exception as e:
        logger.error(f"Error adding members to set {key}: {str(e)}")
        return 0

async def srem(key: str, *members: Any) -> int:
    """Remove members from a set.
    
    Args:
        key: Set key
        *members: One or more members to remove from the set
        
    Returns:
        int: Number of members removed from the set
    """
    client = await get_redis_client()
    if client is None:
        logger.warning(f"Failed to remove members from set {key}: Redis client not available")
        return 0
    
    try:
        serialized_members = [json.dumps(m, cls=UUIDEncoder) if not isinstance(m, (str, int, float, bool)) else m for m in members]
        result = await client.srem(key, *serialized_members)
        return result
    except Exception as e:
        logger.error(f"Error removing members from set {key}: {str(e)}")
        return 0

async def smembers(key: str) -> Set[Any]:
    """Get all members of a set.
    
    Args:
        key: Set key
        
    Returns:
        Set[Any]: All members of the set
    """
    client = await get_redis_client()
    if client is None:
        logger.warning(f"Failed to get members from set {key}: Redis client not available")
        return builtin_set()  # Use the renamed built-in set
    
    try:
        result = await client.smembers(key)
        deserialized_result = builtin_set()  # Use the renamed built-in set
        for item in result:
            if isinstance(item, bytes):
                item = item.decode('utf-8')
            try:
                deserialized_result.add(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                deserialized_result.add(item)
        return deserialized_result
    except Exception as e:
        logger.error(f"Error getting members from set {key}: {str(e)}")
        return builtin_set()  # Use the renamed built-in set

async def sismember(key: str, member: Any) -> bool:
    """Check if a member exists in a set.
    
    Args:
        key: Set key
        member: Member to check
        
    Returns:
        bool: True if member exists in set, False otherwise
    """
    client = await get_redis_client()
    if client is None:
        logger.warning(f"Failed to check member in set {key}: Redis client not available")
        return False
    
    try:
        # Serialize member if it's not a primitive type
        serialized_member = json.dumps(member, cls=UUIDEncoder) if not isinstance(member, (str, int, float, bool)) else member
        result = await client.sismember(key, serialized_member)
        return bool(result)
    except Exception as e:
        logger.error(f"Error checking member in set {key}: {str(e)}")
        return False

# Backward compatibility for code that uses the service instance
async def get_redis_service():
    """Get Redis service instance.
    
    Returns a singleton instance of the Redis service.
    If Redis is not available, returns a null-safe implementation.
    """
    # Use a flag to prevent recursion
    if getattr(get_redis_service, "_in_progress", False):
        logger.warning("Detected potential recursion in Redis service initialization, returning null-safe implementation")
        return create_null_safe_redis_service()
        
    # Set in-progress flag
    setattr(get_redis_service, "_in_progress", True)
    
    try:
        # Try to get a Redis service instance
        return await RedisService.get_instance()
    except Exception as e:
        # Log the error and return a null-safe implementation
        logger.warning(f"Failed to get Redis service: {str(e)}")
        logger.warning("Using null-safe Redis implementation as fallback")
        return create_null_safe_redis_service()
    finally:
        # Always clear the in-progress flag
        setattr(get_redis_service, "_in_progress", False)

def create_null_safe_redis_service():
    """Create a minimal working Redis service instance that handles null client operations safely.
    
    This function creates a RedisService instance with proper null handling,
    ensuring methods don't raise errors when Redis is not available.
    
    Returns:
        RedisService: A null-safe Redis service instance
    """
    service = RedisService()
    service._initialized = True
    service._client = None
    
    # Override methods to handle null client safely
    original_get = service.get
    original_set = service.set
    
    async def safe_get(key, default=None):
        if service._client is None:
            logger.debug(f"Null-safe get for key {key} (Redis unavailable)")
            return default
        return await original_get(key, default)
    
    async def safe_set(key, value, ex=None, nx=False, xx=False):
        if service._client is None:
            logger.debug(f"Null-safe set for key {key} (Redis unavailable)")
            return False
        return await original_set(key, value, ex, nx, xx)
    
    # Replace with safe versions
    service.get = safe_get
    service.set = safe_set
    
    return service

# Add a mock pipeline class for testing
class MockRedisPipeline:
    """Mock Redis pipeline for testing."""
    
    def __init__(self):
        self.commands = []
        
    async def set(self, key, value, ex=None, nx=False, xx=False):
        """Add a set command to the pipeline."""
        self.commands.append(('set', key, value, ex, nx, xx))
        return self
        
    async def get(self, key):
        """Add a get command to the pipeline."""
        self.commands.append(('get', key))
        return self
        
    async def delete(self, key):
        """Add a delete command to the pipeline."""
        self.commands.append(('delete', key))
        return self
        
    async def execute(self):
        """Execute the pipeline.
        
        In mock mode, this just returns a list of None values with the same
        length as the commands list.
        """
        return [None] * len(self.commands) 