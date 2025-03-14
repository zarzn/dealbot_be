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
    # Get the mock Redis service
    mock_redis_service = await get_redis_service_mock()
    
    # Patch the get_redis_service function to return our mock
    with patch('core.services.redis.get_redis_service', return_value=mock_redis_service) as _:
        # Reset the mock Redis state
        if hasattr(mock_redis_service, '_client') and mock_redis_service._client:
            await mock_redis_service._client.flushdb()
        
        logger.info("Redis mock initialized for feature test")
        yield
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