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
        """Set a key-value pair in Redis with optional expiration.
        
        Args:
            key: The key to set
            value: The value to set (will be JSON serialized)
            ex: Optional expiration time in seconds
            nx: Only set if the key does not exist
            xx: Only set if the key already exists
        
        Returns:
            True if the operation was successful, False otherwise
        """
        try:
            if self._client is None:
                await self.init()
            
            # Safely serialize value to JSON
            try:
                # For simple values, use direct serialization
                if isinstance(value, (str, int, float, bool)) or value is None:
                    serialized = value
                else:
                    # First try with normal encoding depth to preserve structure when possible
                    max_depth = _max_encoding_depth.get()
                    try:
                        _max_encoding_depth.set(0)  # Reset the counter
                        serialized = json.dumps(value, cls=UUIDEncoder)
                    except (RecursionError, TypeError, ValueError, json.JSONDecodeError, OverflowError) as json_error:
                        # If normal encoding fails due to recursion, retry with lower max depth
                        logger.warning(f"Initial serialization failed for key {key}, retrying with simplified encoding: {str(json_error)}")
                        _max_encoding_depth.set(0)  # Reset the counter
                        try:
                            # For extremely complex objects, use a more aggressive simplification
                            # Create a simplified representation of the object
                            simple_value = self._simplify_object(value)
                            serialized = json.dumps(simple_value, cls=UUIDEncoder)
                        except Exception as inner_e:
                            logger.error(f"Simplified serialization also failed for key {key}: {str(inner_e)}")
                            # As a last resort, convert to string representation
                            serialized = str(value)
                    finally:
                        # Reset the depth counter to its original value
                        _max_encoding_depth.set(max_depth)
            except Exception as e:
                logger.error(f"Failed to serialize value for key {key}: {str(e)}")
                # Fall back to string representation if serialization fails
                serialized = str(value)
            
            return await self._client.set(key, serialized, ex=ex, nx=nx, xx=xx)
        except Exception as e:
            logger.error(f"Failed to set key {key} in Redis: {str(e)}")
            return False
    
    async def _simplify_object(self, obj: Any) -> Any:
        """Create a simplified representation of an object suitable for serialization.
        
        This is a more aggressive simplification than the UUIDEncoder provides.
        It's used as a fallback for very complex objects.
        """
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
            
        if isinstance(obj, (list, tuple)):
            # Limit list/tuple size and simplify each item
            simplified = []
            for i, item in enumerate(obj):
                if i >= 20:  # Aggressive limit
                    simplified.append(f"<{len(obj) - 20} more items>")
                    break
                simplified.append(self._simplify_object(item))
            return simplified
            
        if isinstance(obj, dict):
            # For dictionaries, simplify keys and values
            simplified = {}
            for i, (key, value) in enumerate(obj.items()):
                if i >= 20:  # Aggressive limit
                    simplified['...'] = f"<{len(obj) - 20} more items>"
                    break
                    
                # Skip private keys and callable values
                if isinstance(key, str) and key.startswith('_'):
                    continue
                if callable(value):
                    continue
                    
                # Use string representation for non-primitive keys
                if not isinstance(key, (str, int, float, bool)):
                    str_key = str(key)
                else:
                    str_key = key
                    
                # Simplify the value
                simplified[str_key] = self._simplify_object(value)
            return simplified
            
        if isinstance(obj, UUID):
            return str(obj)
            
        if isinstance(obj, Decimal):
            return float(obj)
            
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
            
        if isinstance(obj, (set, frozenset)):
            return list(obj)
            
        if inspect.isasyncgen(obj) or inspect.iscoroutine(obj) or inspect.isawaitable(obj):
            return f"<{type(obj).__name__} object>"
            
        if inspect.isgenerator(obj) or inspect.isgeneratorfunction(obj):
            return f"<{type(obj).__name__} object>"
            
        if hasattr(obj, '__dict__') and not isinstance(obj, type):
            # For objects with __dict__, create a simplified dictionary
            simplified = {}
            simplified['__type__'] = type(obj).__name__
            # Add a few key attributes for identification
            for key in list(obj.__dict__.keys())[:10]:
                if key.startswith('_'):
                    continue
                try:
                    value = getattr(obj, key)
                    if callable(value):
                        continue
                    if isinstance(value, (str, int, float, bool, type(None))):
                        simplified[key] = value
                    else:
                        # Just use type name for complex values
                        simplified[key] = f"<{type(value).__name__}>"
                except Exception:
                    continue
            return simplified
            
        # Final fallback - just return the string representation
        try:
            return f"<{type(obj).__name__}: {str(obj)[:100]}>"
        except Exception:
            return f"<{type(obj).__name__}>"
    
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
        return await set(key, value, ex=seconds)
    
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
                if password in ["your_redis_password", "your_production_redis_password"]:
                    password = None

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
        return _redis_client
    
    # Check for recursion to prevent infinite loops
    if getattr(get_redis_client, "_in_progress", False):
        logger.debug("Recursion detected in get_redis_client() call")
        return None
        
    # Set recursion guard
    get_redis_client._in_progress = True
    
    try:
        # In testing mode, return None without trying to connect
        if getattr(settings, "TESTING", False):
            logger.debug("In testing mode - returning None for Redis client")
            _initialized = True
            return None
        
        # Check if Redis is disabled in configuration
        redis_disabled = getattr(settings, "REDIS_DISABLED", False)
        if redis_disabled:
            logger.debug("Redis is disabled in configuration - returning None")
            _initialized = True
            return None
            
        # Try to get Redis configuration
        redis_host = getattr(settings, "REDIS_HOST", None)
        redis_port = getattr(settings, "REDIS_PORT", 6379)
        redis_db = getattr(settings, "REDIS_DB", 0)
        
        # If we don't have a host, we can't connect
        if not redis_host:
            logger.debug("No Redis host configured, Redis will be disabled")
            _initialized = True
            return None
            
        # Get password, handling default values
        password = getattr(settings, "REDIS_PASSWORD", None)
        if password in ["your_redis_password", "your_production_redis_password", None, ""]:
            # Use None for password if it's not set or is a default value
            password = None
        
        # Use the pool if it exists, otherwise create a new one
        if _redis_pool is None:
            # Create connection pool with best practice configurations
            _redis_pool = ConnectionPool(
                host=redis_host,
                port=int(redis_port),  # Ensure port is an integer
                db=int(redis_db),      # Ensure db is an integer
                password=password,
                max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 10),
                socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT", 5),
                socket_connect_timeout=getattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT", 5),
                retry_on_timeout=getattr(settings, "REDIS_RETRY_ON_TIMEOUT", True),
                health_check_interval=getattr(settings, "REDIS_HEALTH_CHECK_INTERVAL", 30),
                decode_responses=True,
                encoding="utf-8"
            )
        
        # Create Redis client with the pool
        _redis_client = Redis(connection_pool=_redis_pool)
        
        # Test the connection with a timeout to avoid hanging
        try:
            ping_result = await asyncio.wait_for(_redis_client.ping(), timeout=2.0)
            if ping_result:
                logger.info("Successfully connected to Redis")
            else:
                logger.warning("Redis ping returned False, connection may not be working properly")
                _redis_client = None
        except (asyncio.TimeoutError, ConnectionError) as e:
            logger.warning(f"Redis connection failed: {str(e)}")
            _redis_client = None
        except Exception as e:
            logger.warning(f"Error testing Redis connection: {str(e)}")
            _redis_client = None
            
        # Mark as initialized even if connection failed, to avoid repeated attempts
        _initialized = True
        
        # Only log this message once
        if _redis_client is None and not hasattr(get_redis_client, "_warned_no_redis"):
            logger.info("Continuing without Redis functionality")
            get_redis_client._warned_no_redis = True
            
        return _redis_client
            
    except ImportError:
        if not hasattr(get_redis_client, "_warned_import_error"):
            logger.warning("Redis package not installed - Redis functionality will be disabled")
            get_redis_client._warned_import_error = True
        _initialized = True
        return None
        
    except Exception as e:
        if not hasattr(get_redis_client, "_warned_general_error"):
            logger.warning(f"Error initializing Redis client: {str(e)}")
            get_redis_client._warned_general_error = True
        _initialized = True
        return None
    finally:
        # Always reset recursion guard
        get_redis_client._in_progress = False

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
    """Set JSON value in Redis."""
    client = await get_redis_client()
    
    if client is None:
        return False
        
    try:
        # Convert value to JSON string
        json_value = json.dumps(value, cls=UUIDEncoder)
        
        # Set value in Redis
        result = await client.set(key, json_value)
        
        # Set expiration if provided
        if ex is not None and result:
            seconds = ex if isinstance(ex, int) else int(ex.total_seconds())
            await client.expire(key, seconds)
            
        return bool(result)
    except Exception as e:
        logger.error(f"Error setting Redis JSON value for {key}: {str(e)}")
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
    
    This function follows the singleton pattern to ensure only
    one Redis service is created. It includes error handling,
    logging, and fallback mechanisms.
    
    Returns:
        RedisService: Configured Redis service instance
    """
    # Static variables to track warning states and last attempt
    if not hasattr(get_redis_service, "_warned_no_redis"):
        get_redis_service._warned_no_redis = False
        
    if not hasattr(get_redis_service, "_last_init_attempt"):
        get_redis_service._last_init_attempt = 0
    
    # Rate limit initialization attempts (once every 5 seconds max)
    current_time = time.time()
    if (current_time - get_redis_service._last_init_attempt) < 5:
        # Return existing instance or minimal working instance silently
        try:
            service = await RedisService.get_instance()
            return service
        except Exception:
            # If the instance retrieval fails, return a minimal working instance
            service = RedisService()
            service._initialized = True
            service._client = None
            return service
    
    # Record the attempt time
    get_redis_service._last_init_attempt = current_time
    
    try:
        # Try to get a Redis client first to ensure connection is available
        redis_client = await get_redis_client()
        
        # Get or create the instance through the class method
        service = await RedisService.get_instance()
        
        # Verify Redis is working, but only log a warning once
        if service._client is None:
            if not get_redis_service._warned_no_redis:
                logger.warning("Redis client not initialized, some features may be limited")
                get_redis_service._warned_no_redis = True
            
            # Try to re-initialize with fresh client
            if redis_client is not None:
                try:
                    await service.init(client=redis_client)
                    logger.info("Successfully re-initialized Redis service")
                    get_redis_service._warned_no_redis = False
                except Exception as reinit_error:
                    logger.warning(f"Failed to re-initialize Redis service: {str(reinit_error)}")
        else:
            # Successfully initialized with working client
            if get_redis_service._warned_no_redis:
                logger.info("Redis service is now working properly")
                get_redis_service._warned_no_redis = False
        
        return service
    except Exception as e:
        # Log error but provide a minimal working instance (only log once)
        if not get_redis_service._warned_no_redis:
            logger.warning(f"Error getting Redis service: {str(e)}")
            get_redis_service._warned_no_redis = True
        
        # Create a minimal working instance
        service = RedisService()
        service._initialized = True
        service._client = None
        
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