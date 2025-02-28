"""Configure feature test environment."""

import pytest
import logging
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from backend_tests.mocks.redis_mock import redis_mock, get_mock_redis_service
from core.services.redis import get_redis_service, RedisService
from backend_tests.mocks.redis_service_mock import get_redis_service_mock

logger = logging.getLogger(__name__)

@pytest.fixture(scope="function", autouse=True)
async def mock_redis_for_features():
    """Mock Redis for all feature tests.
    
    This fixture is automatically applied to all feature tests to ensure
    that Redis operations use a mock implementation instead of trying to
    connect to a real Redis server.
    """
    # Patch both the get_redis_service function AND the RedisService initialization
    with patch('core.services.redis.get_redis_service', return_value=get_mock_redis_service()) as _:
        with patch('core.services.redis.RedisService._client', redis_mock):
            # Reset the mock Redis state
            await redis_mock.flushdb()
            
            # Pre-populate with test data if needed
            await redis_mock.set("test_key", "test_value")
            
            # Add task metadata for test expectations
            for i in range(3):
                task_key = f"task:task_{i}"
                task_data = {
                    "id": f"task_{i}",
                    "status": "completed",
                    "created_at": "2025-02-27T08:00:00+00:00",
                    "completed_at": "2025-02-27T08:01:00+00:00"
                }
                await redis_mock.set(task_key, task_data)
            
            logger.info("Redis mock initialized for feature test")
            yield
            
            # Cleanup
            await redis_mock.flushdb()
            logger.info("Redis mock cleaned up after feature test")

@pytest.fixture(scope="function")
async def redis_client() -> Redis:
    """Create a Redis client using the mock implementation.
    
    Returns:
        Redis: Mock Redis client for tests
    """
    # Reset the mock Redis state
    await redis_mock.flushdb()
    return redis_mock

@pytest.fixture(scope="function")
async def redis_service() -> RedisService:
    """Create a RedisService instance using the mock Redis client.
    
    Returns:
        RedisService: Redis service initialized with the mock client
    """
    service = await get_redis_service_mock()
    return service 