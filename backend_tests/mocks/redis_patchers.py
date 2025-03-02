"""Redis patchers for testing.

This module provides functions to patch the Redis service with a mock implementation.
"""

import logging
from unittest.mock import patch, AsyncMock
from typing import Any, Dict, Optional

from .redis_mock import RedisMock

logger = logging.getLogger(__name__)

# Create a singleton instance of RedisMock
redis_mock = RedisMock()

def patch_redis_service():
    """Patch the Redis service with a mock implementation.
    
    Returns:
        patch: The patch object that can be used to stop the patch.
    """
    try:
        # Import here to avoid circular imports
        from core.services.redis import RedisService
        
        # Create a patched version of the RedisService
        original_init = RedisService.__init__
        original_get_instance = RedisService.get_instance
        
        async def patched_init(self):
            """Patched init method that sets up the mock client."""
            self._prefix = "cache:"
            self._client = redis_mock
            
        async def patched_get_instance(cls):
            """Patched get_instance method that returns the instance with mock client."""
            if cls._instance is None:
                cls._instance = cls()
                cls._instance._client = redis_mock
            return cls._instance
        
        # Apply the patches
        RedisService.__init__ = patched_init
        RedisService.get_instance = classmethod(patched_get_instance)
        
        # Return a patch object that can be used to stop the patch
        return patch('core.services.redis.RedisService', RedisService)
    except Exception as e:
        logger.error(f"Error patching Redis service: {str(e)}")
        # Return a dummy patch that does nothing
        return patch('unittest.mock.Mock', lambda: None)

def get_mock_redis_service():
    """Get a mock Redis service instance.
    
    Returns:
        RedisMock: The Redis mock instance.
    """
    return redis_mock 