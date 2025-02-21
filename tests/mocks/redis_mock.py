"""Redis mock for testing."""

import json
import time
from typing import Any, Dict, List, Optional, Union, AsyncIterator, Tuple
from datetime import datetime, timedelta
import fnmatch
import logging

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Raised when Redis authentication fails."""
    pass

class RedisPipelineMock:
    """Mock Redis pipeline for testing."""
    
    def __init__(self, redis_mock: 'RedisMock'):
        """Initialize pipeline mock."""
        self._redis = redis_mock
        self._commands = []
        self._prefix = "cache:"  # Match RedisClient prefix

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> 'RedisPipelineMock':
        """Add set command to pipeline."""
        self._commands.append(('set', (self._prefix + key, value, ex)))
        return self

    async def incrby(self, key: str, amount: int = 1) -> 'RedisPipelineMock':
        """Add incrby command to pipeline."""
        self._commands.append(('incrby', (self._prefix + key, amount)))
        return self

    async def zadd(self, key: str, mapping: Dict[str, float]) -> 'RedisPipelineMock':
        """Add zadd command to pipeline."""
        self._commands.append(('zadd', (key, mapping)))
        return self

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> 'RedisPipelineMock':
        """Add zremrangebyscore command to pipeline."""
        self._commands.append(('zremrangebyscore', (key, min_score, max_score)))
        return self

    async def expire(self, key: str, seconds: int) -> 'RedisPipelineMock':
        """Add expire command to pipeline."""
        self._commands.append(('expire', (key, seconds)))
        return self

    async def execute(self) -> List[Any]:
        """Execute all commands in pipeline."""
        results = []
        for cmd, args in self._commands:
            if cmd == 'set':
                key, value, ex = args
                results.append(await self._redis.set(key, value, ex=ex))
            elif cmd == 'incrby':
                key, amount = args
                results.append(await self._redis.incrby(key, amount))
            elif cmd == 'zadd':
                key, mapping = args
                results.append(await self._redis.zadd(key, mapping))
            elif cmd == 'zremrangebyscore':
                key, min_score, max_score = args
                results.append(await self._redis.zremrangebyscore(key, min_score, max_score))
            elif cmd == 'expire':
                key, seconds = args
                results.append(await self._redis.expire(key, seconds))
        self._commands.clear()
        return results

class RedisMock:
    """Mock Redis client for testing."""

    def __init__(self):
        """Initialize mock Redis client."""
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._is_authenticated = False
        self._keys = []
        self._current_key_index = 0
        self._counters: Dict[str, int] = {}
        self._zsets: Dict[str, Dict[str, float]] = {}  # For sorted sets

    async def auth(self, password: str) -> bool:
        """Authenticate with Redis."""
        self._is_authenticated = True
        return True

    async def get(self, key: str) -> Optional[str]:
        """Get value from mock Redis."""
        if key in self._expiry and time.time() > self._expiry[key]:
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in mock Redis."""
        try:
            if isinstance(value, (dict, list)):
                self._data[key] = json.dumps(value)
            else:
                self._data[key] = str(value)
            
            if ex is not None:
                self._expiry[key] = time.time() + ex
            return True
        except Exception:
            return False

    async def setex(self, key: str, time_seconds: int, value: Any) -> bool:
        """Set value with expiration in mock Redis."""
        return await self.set(key, value, ex=time_seconds)

    async def delete(self, *keys: str) -> bool:
        """Delete one or more keys from mock Redis."""
        try:
            deleted = False
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    if key in self._expiry:
                        del self._expiry[key]
                    deleted = True
                if key in self._zsets:
                    del self._zsets[key]
                    deleted = True
            return True  # Always return True to match Redis behavior
        except Exception:
            return False

    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment counter by amount."""
        try:
            if key not in self._counters:
                self._counters[key] = 0
            self._counters[key] += amount
            self._data[key] = str(self._counters[key])  # Update data for get operations
            return self._counters[key]
        except Exception:
            return 0

    async def zadd(self, key: str, mapping: Dict[str, float]) -> bool:
        """Add one or more members to a sorted set."""
        try:
            if key not in self._zsets:
                self._zsets[key] = {}
            self._zsets[key].update(mapping)
            return True
        except Exception:
            return False

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> bool:
        """Remove members from sorted set with scores within the given range."""
        try:
            if key not in self._zsets:
                return True
            self._zsets[key] = {
                member: score
                for member, score in self._zsets[key].items()
                if score < min_score or score > max_score
            }
            return True
        except Exception:
            return False

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with scores within the given range."""
        try:
            if key not in self._zsets:
                return 0
            return len([
                score
                for score in self._zsets[key].values()
                if min_score <= score <= max_score
            ])
        except Exception:
            return 0

    async def zrange(self, key: str, start: int, stop: int, withscores: bool = False) -> List[Union[str, Tuple[str, float]]]:
        """Get range of members from sorted set."""
        try:
            if key not in self._zsets:
                return []
            items = sorted(self._zsets[key].items(), key=lambda x: x[1])
            if start < 0:
                start = max(0, len(items) + start)
            if stop < 0:
                stop = max(0, len(items) + stop)
            else:
                stop = min(len(items), stop + 1)
            items = items[start:stop]
            if withscores:
                return items
            return [item[0] for item in items]
        except Exception:
            return []

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            if key in self._data or key in self._zsets:
                self._expiry[key] = time.time() + seconds
                return True
            return False
        except Exception:
            return False

    async def ping(self) -> bool:
        """Check mock Redis connection."""
        return True

    async def close(self) -> None:
        """Close mock Redis connection."""
        self._data.clear()
        self._expiry.clear()
        self._is_authenticated = False
        self._keys.clear()
        self._current_key_index = 0
        self._counters.clear()
        self._zsets.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def pipeline(self) -> RedisPipelineMock:
        """Create a pipeline."""
        return RedisPipelineMock(self)

    async def scan(self, cursor: int = 0, match: Optional[str] = None) -> Tuple[int, List[str]]:
        """Scan keys matching pattern."""
        pattern = match.replace("*", "") if match else ""
        matching_keys = [k for k in self._data.keys() if pattern in k]
        return 0, matching_keys

    async def __aiter__(self):
        """Async iterator implementation."""
        return self

    async def __anext__(self):
        """Get next item in async iteration."""
        return self  # Return self for rate limiting test

class AsyncRedisMock:
    """Async Redis mock for testing."""
    
    def __init__(self):
        """Initialize mock Redis client."""
        self._data = {}
        self._expiry = {}
        self._zsets = {}
        self._counters = {}
        self._is_authenticated = False

    async def auth(self, password: str) -> bool:
        """Authenticate with Redis."""
        self._is_authenticated = True
        return True

    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: Optional[int] = None) -> Tuple[int, List[str]]:
        """Scan keys matching pattern."""
        try:
            pattern = match.replace("*", "") if match else ""
            matching_keys = [k for k in self._data.keys() if pattern in k]
            return 0, matching_keys
        except Exception as e:
            logger.error(f"Error in scan: {str(e)}")
            return 0, []

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with scores within the given range."""
        try:
            if key not in self._zsets:
                return 0
            count = len([
                score
                for score in self._zsets[key].values()
                if min_score <= score <= max_score
            ])
            return count
        except Exception as e:
            logger.error(f"Error in zcount: {str(e)}")
            return 0

    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Add to sorted set."""
        try:
            if key not in self._zsets:
                self._zsets[key] = {}
            self._zsets[key].update(mapping)
            return len(mapping)
        except Exception as e:
            logger.error(f"Error in zadd: {str(e)}")
            return 0

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove range from sorted set by score."""
        try:
            if key not in self._zsets:
                return 0
            removed = 0
            to_remove = []
            for member, score in self._zsets[key].items():
                if min_score <= score <= max_score:
                    to_remove.append(member)
                    removed += 1
            for member in to_remove:
                del self._zsets[key][member]
            return removed
        except Exception as e:
            logger.error(f"Error in zremrangebyscore: {str(e)}")
            return 0

    async def pipeline(self):
        """Create a pipeline."""
        return AsyncRedisPipelineMock(self)

    async def get(self, key: str) -> Optional[str]:
        """Get value for key."""
        try:
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._data[key]
                del self._expiry[key]
                return None
            return self._data.get(key)
        except Exception as e:
            logger.error(f"Error in get: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set key with value."""
        try:
            if nx and key in self._data:
                return False
            if xx and key not in self._data:
                return False
            
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self._data[key] = value
            
            if ex:
                self._expiry[key] = time.time() + ex
            elif px:
                self._expiry[key] = time.time() + (px / 1000.0)
            
            return True
        except Exception as e:
            logger.error(f"Error in set: {str(e)}")
            return False

    async def delete(self, *keys: str) -> int:
        """Delete key."""
        try:
            deleted = 0
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    if key in self._expiry:
                        del self._expiry[key]
                    deleted += 1
                if key in self._zsets:
                    del self._zsets[key]
                    deleted += 1
            return deleted
        except Exception as e:
            logger.error(f"Error in delete: {str(e)}")
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on key."""
        try:
            if key in self._data or key in self._zsets:
                self._expiry[key] = time.time() + seconds
                return True
            return False
        except Exception as e:
            logger.error(f"Error in expire: {str(e)}")
            return False

    async def ping(self) -> bool:
        """Check Redis connection."""
        return True

    async def close(self) -> None:
        """Close Redis connection."""
        self._data.clear()
        self._expiry.clear()
        self._zsets.clear()
        self._counters.clear()
        self._is_authenticated = False

class AsyncRedisPipelineMock:
    """Async Redis pipeline mock."""
    
    def __init__(self, redis_mock: AsyncRedisMock):
        """Initialize pipeline mock."""
        self._redis = redis_mock
        self._commands = []

    async def execute(self) -> List[Any]:
        """Execute all commands in pipeline."""
        results = []
        for cmd, args, kwargs in self._commands:
            method = getattr(self._redis, cmd)
            results.append(await method(*args, **kwargs))
        self._commands.clear()
        return results

    def __getattr__(self, name):
        """Handle unknown method calls."""
        async def wrapper(*args, **kwargs):
            self._commands.append((name, args, kwargs))
            return self
        return wrapper