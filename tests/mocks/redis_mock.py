"""Redis mock for testing."""

from typing import Any, Dict, Optional
import json

class AsyncRedisMock:
    """Mock Redis client for testing."""

    def __init__(self):
        """Initialize mock Redis."""
        self.data = {}
        self.pipeline_commands = []

    async def get(self, key: str):
        """Get value for key."""
        return self.data.get(key)

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Set key to value with optional expiration."""
        self.data[key] = value
        if expire:
            await self.expire(key, expire)

    async def incrby(self, key: str, amount: int = 1):
        """Increment value by amount."""
        if key not in self.data:
            self.data[key] = 0
        self.data[key] += amount
        return self.data[key]

    async def expire(self, key: str, seconds: int):
        """Set expiration for key."""
        # In the mock, we don't actually implement expiration
        pass

    def pipeline(self):
        """Get a pipeline object."""
        return AsyncPipelineMock(self)

class AsyncPipelineMock:
    """Mock Redis pipeline for testing."""

    def __init__(self, redis_mock: AsyncRedisMock):
        self.redis_mock = redis_mock
        self.commands = []

    async def __aenter__(self):
        """Enter the async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context and execute commands."""
        if not exc_type:
            for cmd, args, kwargs in self.commands:
                await getattr(self.redis_mock, cmd)(*args, **kwargs)
        return None

    def incrby(self, key: str, amount: int = 1):
        """Add incrby command to pipeline."""
        self.commands.append(('incrby', (key, amount), {}))
        return self

    def expire(self, key: str, seconds: int):
        """Add expire command to pipeline."""
        self.commands.append(('expire', (key, seconds), {}))
        return self

    async def execute(self):
        """Execute all commands in the pipeline."""
        results = []
        for cmd, args, kwargs in self.commands:
            result = await getattr(self.redis_mock, cmd)(*args, **kwargs)
            results.append(result)
        self.commands = []  # Clear commands after execution
        return results 