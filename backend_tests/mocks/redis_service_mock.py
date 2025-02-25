"""Redis service mocking for tests."""

import logging
from typing import Optional
from core.services.redis import RedisService

from backend_tests.mocks.redis_mock import redis_mock

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
        # Initialize with our redis_mock
        await redis_service_instance.init(client=redis_mock)
        logger.info("Initialized Redis service with mock client")
    
    return redis_service_instance 