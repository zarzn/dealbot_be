"""Redis service mocking for tests."""

import logging
from typing import Optional
from core.services.redis import RedisService

from backend_tests.mocks.redis_mock import redis_mock, RedisMock

logger = logging.getLogger(__name__)

# Global instance
redis_service_instance: Optional[RedisService] = None

async def get_redis_service_mock() -> RedisService:
    """Get mocked Redis service instance.
    
    This function replaces the original get_redis_service function
    during tests to use our RedisMock implementation instead of 
    a real Redis connection.
    """
    global redis_service_instance
    
    if redis_service_instance is None:
        # Create a new instance of RedisService
        redis_service_instance = RedisService()
        
        # Ensure redis_mock is properly initialized
        if not hasattr(redis_mock, 'blacklist') or redis_mock.blacklist is None:
            redis_mock.blacklist = {}
            
        # Initialize with our redis_mock
        await redis_service_instance.init(client=redis_mock)
        
        # Ensure the client is set
        if redis_service_instance._client is None:
            redis_service_instance._client = redis_mock
            
        # Add direct access to blacklist methods
        redis_service_instance.blacklist_token = redis_mock.blacklist_token
        redis_service_instance.is_token_blacklisted = redis_mock.is_token_blacklisted
        
        logger.info("Initialized Redis service with mock client")
    else:
        # Ensure the client is still set (in case it was reset)
        if redis_service_instance._client is None:
            redis_service_instance._client = redis_mock
    
    return redis_service_instance 