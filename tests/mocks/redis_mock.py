"""Redis mock for testing."""

from typing import Dict, Any, Optional
import json

class AsyncRedisMock:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self.data = {}
        self.pipeline_commands = []
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from mock Redis."""
        if key in self.data:
            value = self.data[key]
            try:
                return json.loads(value)
            except:
                return value
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> None:
        """Set value in mock Redis."""
        if isinstance(value, (dict, list)):
            self.data[key] = json.dumps(value)
        else:
            self.data[key] = value
    
    async def incrby(self, key: str, amount: int = 1) -> int:
        """Increment value in mock Redis."""
        if key not in self.data:
            self.data[key] = "0"
        
        current = int(self.data[key])
        new_value = current + amount
        self.data[key] = str(new_value)
        return new_value
    
    async def expire(self, key: str, seconds: int) -> None:
        """Mock expire command."""
        pass  # We don't implement actual expiration in mock
    
    def pipeline(self):
        """Get pipeline mock."""
        return AsyncRedisPipelineMock(self)

class AsyncRedisPipelineMock:
    """Mock Redis pipeline for testing."""
    
    def __init__(self, redis_mock: AsyncRedisMock):
        self.redis_mock = redis_mock
        self.commands = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def incrby(self, key: str, amount: int = 1):
        """Add incrby command to pipeline."""
        self.commands.append(('incrby', key, amount))
        return self
    
    async def expire(self, key: str, seconds: int):
        """Add expire command to pipeline."""
        self.commands.append(('expire', key, seconds))
        return self
    
    async def execute(self):
        """Execute pipeline commands."""
        results = []
        for cmd, *args in self.commands:
            if cmd == 'incrby':
                result = await self.redis_mock.incrby(*args)
                results.append(result)
            elif cmd == 'expire':
                await self.redis_mock.expire(*args)
                results.append(True)
        
        self.commands = []  # Clear commands after execution
        return results 