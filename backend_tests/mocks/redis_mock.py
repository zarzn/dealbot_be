"""Redis mock for testing purposes.

This module provides a mock implementation of Redis for unit testing.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
import asyncio
from unittest.mock import MagicMock

from core.exceptions import RedisError, CacheOperationError

logger = logging.getLogger(__name__)

class RedisMock:
    """Mock Redis client for testing."""
    
    def __init__(self):
        """Initialize Redis mock with empty storage."""
        self.data = {}
        self.expiry = {}
        self.connected = True
        self.closed = False
        self.blacklist = {}
        self.rate_limits = {}
        self.lists = {}
        self.prefix = "cache:"
    
    async def close(self) -> None:
        """Close the Redis connection."""
        self.connected = False
        self.closed = True
    
    async def get(self, key: str) -> Any:
        """Get value from mock Redis."""
        try:
            # Check if the key is expired
            if key in self.expiry and self.expiry[key] < datetime.now().timestamp():
                del self.data[key]
                del self.expiry[key]
                return None
            
            if key in self.data:
                return self.data[key]
            return None
        except Exception as e:
            logger.error(f"Error getting Redis key {key}: {str(e)}")
            raise RedisError(f"Redis get operation failed: {str(e)}")
    
    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in mock Redis."""
        try:
            self.data[key] = value
            if ex:
                self.expiry[key] = datetime.now().timestamp() + ex
            return True
        except Exception as e:
            logger.error(f"Error setting Redis key {key}: {str(e)}")
            raise RedisError(f"Redis set operation failed: {str(e)}")
    
    async def setex(self, key: str, time: int, value: Any) -> bool:
        """Set value with expiration in mock Redis."""
        return await self.set(key, value, ex=time)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys from mock Redis."""
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                if key in self.expiry:
                    del self.expiry[key]
                count += 1
        return count
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in mock Redis."""
        # Check if the key is expired
        if key in self.expiry and self.expiry[key] < datetime.now().timestamp():
            del self.data[key]
            del self.expiry[key]
            return False
        
        return key in self.data
    
    async def flushdb(self) -> bool:
        """Clear all data in mock Redis."""
        self.data.clear()
        self.expiry.clear()
        self.blacklist.clear()
        self.lists.clear()
        return True
    
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the beginning of a list."""
        if key not in self.lists:
            self.lists[key] = []
        
        for value in values:
            self.lists[key].insert(0, value)
        
        return len(self.lists[key])
    
    async def rpush(self, key: str, *values: str) -> int:
        """Push values to the end of a list."""
        if key not in self.lists:
            self.lists[key] = []
        
        for value in values:
            self.lists[key].append(value)
        
        return len(self.lists[key])
    
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get a range of elements from a list."""
        if key not in self.lists:
            return []
        
        # Handle negative indices
        if end == -1:
            end = len(self.lists[key])
        
        return self.lists[key][start:end]
    
    async def expire(self, key: str, time: int) -> bool:
        """Set an expiration on a key."""
        if key in self.data:
            self.expiry[key] = datetime.now().timestamp() + time
            return True
        if key in self.lists:
            self.expiry[key] = datetime.now().timestamp() + time
            return True
        return False
    
    async def ping(self) -> bool:
        """Check if Redis is connected."""
        return self.connected
    
    # Token blacklist operations
    async def blacklist_token(self, token: str, expire: int) -> bool:
        """Add token to blacklist."""
        key = f"blacklist:{token}"
        self.blacklist[token] = datetime.now().timestamp() + expire
        return True
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        if token in self.blacklist:
            # Check expiration
            if self.blacklist[token] > datetime.now().timestamp():
                return True
            else:
                del self.blacklist[token]
        return False
    
    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment a key by a value."""
        if key not in self.data:
            self.data[key] = "0"
        
        try:
            value = int(self.data[key])
            value += amount
            self.data[key] = str(value)
            return value
        except (ValueError, TypeError):
            # Key is not an integer
            raise RedisError("Redis key is not an integer")
            
    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: Optional[int] = None) -> Tuple[int, List[str]]:
        """Scan for keys in Redis mock."""
        try:
            matching_keys = []
            
            # If match pattern is provided, filter keys
            if match:
                # Convert Redis glob pattern to simple prefix match for basic implementation
                prefix = match.replace('*', '')
                matching_keys = [key for key in self.data.keys() if key.startswith(prefix)]
            else:
                matching_keys = list(self.data.keys())
            
            # Apply count if specified
            if count and len(matching_keys) > count:
                matching_keys = matching_keys[:count]
            
            # Return 0 to indicate no more keys to scan
            return 0, matching_keys
        except Exception as e:
            logger.error(f"Error scanning Redis keys: {str(e)}")
            raise RedisError(f"Redis scan operation failed: {str(e)}")

    def pipeline(self):
        """Create a pipeline."""
        return PipelineMock(self)

class PipelineMock:
    """Mock Redis pipeline for testing."""
    
    def __init__(self, redis_mock: RedisMock):
        """Initialize pipeline with Redis mock."""
        self.redis_mock = redis_mock
        self.commands = []
    
    async def execute(self):
        """Execute commands in pipeline."""
        results = []
        for command, args, kwargs in self.commands:
            result = await command(*args, **kwargs)
            results.append(result)
        
        self.commands = []
        return results
    
    def get(self, key: str):
        """Add get command to pipeline."""
        self.commands.append((self.redis_mock.get, (key,), {}))
        return self
    
    def set(self, key: str, value: Any, ex: Optional[int] = None):
        """Add set command to pipeline."""
        self.commands.append((self.redis_mock.set, (key, value), {"ex": ex}))
        return self
    
    def delete(self, *keys: str):
        """Add delete command to pipeline."""
        self.commands.append((self.redis_mock.delete, keys, {}))
        return self
    
    def exists(self, key: str):
        """Add exists command to pipeline."""
        self.commands.append((self.redis_mock.exists, (key,), {}))
        return self
    
    def expire(self, key: str, time: int):
        """Add expire command to pipeline."""
        self.commands.append((self.redis_mock.expire, (key, time), {}))
        return self

# Create a singleton instance for easy access
redis_mock = RedisMock()

# Mock the get_redis_service function
async def get_mock_redis_service():
    return redis_mock

# Function to patch the RedisService for tests
def patch_redis_service():
    from unittest.mock import patch
    from core.services.redis import get_redis_service
    
    p = patch('core.services.redis.get_redis_service', get_mock_redis_service)
    p.start()
    return p 