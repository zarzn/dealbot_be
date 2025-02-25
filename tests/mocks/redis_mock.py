"""Redis mock for testing."""

import json
import logging
import asyncio
import fnmatch
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from unittest.mock import AsyncMock, MagicMock

logger = logging.getLogger(__name__)

class RedisError(Exception):
    """Base class for Redis errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class RedisMock:
    """Mock Redis client for testing."""

    def __init__(self):
        """Initialize mock data stores."""
        self.data = {}
        self._blacklist = {}
        self._pipeline = None

    async def init(self):
        """Initialize mock."""
        pass

    async def close(self):
        """Close mock."""
        self.data.clear()
        self._blacklist.clear()

    async def get(self, key: str) -> Any:
        """Get value from mock."""
        return self.data.get(key)

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in mock."""
        self.data[key] = value
        if expire:
            self._blacklist[key] = datetime.utcnow().timestamp() + expire
        return True

    async def delete(self, key: str) -> bool:
        """Delete key from mock."""
        if key in self.data:
            del self.data[key]
            if key in self._blacklist:
                del self._blacklist[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in mock."""
        if key in self._blacklist:
            # Check expiration
            if datetime.utcnow().timestamp() > self._blacklist[key]:
                await self.delete(key)
                return False
        return key in self.data

    async def blacklist_token(self, token: str, expire: int) -> bool:
        """Add token to blacklist."""
        try:
            key = f"blacklist:{token}"
            self.data[key] = "1"
            self._blacklist[key] = datetime.utcnow().timestamp() + expire
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")
            raise RedisError(f"Token blacklist operation failed: {str(e)}")

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        try:
            key = f"blacklist:{token}"
            if key in self._blacklist:
                # Check expiration
                if datetime.utcnow().timestamp() > self._blacklist[key]:
                    await self.delete(key)
                    return False
            return key in self.data
        except Exception as e:
            logger.error(f"Error checking blacklisted token: {str(e)}")
            raise RedisError(f"Token blacklist check failed: {str(e)}")

    async def pipeline(self):
        """Create pipeline mock."""
        self._pipeline = PipelineMock(self)
        return self._pipeline

    async def ping(self) -> bool:
        """Mock ping."""
        return True

class PipelineMock:
    """Mock Redis pipeline."""

    def __init__(self, redis_mock: RedisMock):
        """Initialize pipeline mock."""
        self.redis_mock = redis_mock
        self.commands = []

    def __getattr__(self, name: str):
        """Handle unknown attribute access."""
        async def wrapper(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return wrapper

    async def execute(self):
        """Execute pipeline commands."""
        results = []
        for cmd, args, kwargs in self.commands:
            method = getattr(self.redis_mock, cmd)
            results.append(await method(*args, **kwargs))
        self.commands = []
        return results

# Global mock instance
redis_mock: Optional[RedisMock] = None

def get_redis_mock() -> RedisMock:
    """Get Redis mock instance."""
    global redis_mock
    if redis_mock is None:
        redis_mock = RedisMock()
    return redis_mock