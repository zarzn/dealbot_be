"""Test Redis cache operations.

This module contains test cases for Redis cache operations using a mock Redis implementation.
"""

# Standard library imports
import pytest
import pytest_asyncio
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

# Core imports
from core.utils.redis import RedisClient
from core.exceptions.base_exceptions import RateLimitError

@pytest.fixture
def redis_mock():
    mock = MagicMock()
    # Set up basic mock methods
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=True)
    mock.incrby = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.pipeline = MagicMock()
    mock.setex = AsyncMock(return_value=True)
    mock.scan = AsyncMock(return_value=(0, ["test:1", "test:2"]))
    mock.ping = AsyncMock(return_value=True)
    
    # Set up pipeline mock
    pipeline_mock = MagicMock()
    pipeline_mock.get = AsyncMock()
    pipeline_mock.set = AsyncMock()
    pipeline_mock.incrby = AsyncMock()
    pipeline_mock.execute = AsyncMock(return_value=[True, True, "5"])
    mock.pipeline.return_value = pipeline_mock
    
    return mock

@pytest.fixture
def redis_client(redis_mock):
    with patch('core.utils.redis.get_redis_client', return_value=redis_mock), \
         patch('core.utils.redis.get_redis_pool', return_value=MagicMock()), \
         patch('core.utils.redis._redis_client', new=redis_mock), \
         patch('core.utils.redis._redis_pool', new=MagicMock()):
        client = RedisClient()
        client._client = redis_mock
        return client

@pytest.mark.asyncio
async def test_basic_cache_operations(redis_client, redis_mock):
    """Test basic set, get, and delete operations."""
    test_value = "test_value"
    
    # Test get
    redis_mock.get.return_value = test_value
    result = await redis_client.get("test_key")
    assert result == test_value
    redis_mock.get.assert_called_with("cache:test_key")
    
    # Test set
    await redis_client.set("test_key", test_value)
    redis_mock.set.assert_called_with("cache:test_key", test_value)
    
    # Test delete
    await redis_client.delete("test_key")
    redis_mock.delete.assert_called_with("cache:test_key")

@pytest.mark.asyncio
async def test_cache_with_ttl(redis_client, redis_mock):
    """Test cache operations with TTL."""
    test_value = "test_value"
    ttl = 3600
    
    await redis_client.set("ttl_key", test_value, expire=ttl)
    redis_mock.setex.assert_called_with("cache:ttl_key", ttl, test_value)

@pytest.mark.asyncio
async def test_cache_complex_data(redis_client, redis_mock):
    """Test caching complex data structures."""
    test_data = {"key": "value", "nested": {"data": 123}}
    
    # Test set
    await redis_client.set("complex_key", test_data)
    redis_mock.set.assert_called_once()
    
    # Test get
    redis_mock.get.return_value = '{"key": "value", "nested": {"data": 123}}'
    result = await redis_client.get("complex_key")
    assert result == test_data

@pytest.mark.asyncio
async def test_cache_pattern_operations(redis_client, redis_mock):
    """Test clearing cache by key patterns."""
    test_pattern = "test:*"
    redis_mock.scan.return_value = (0, ["test:1", "test:2"])
    await redis_client.clear_pattern(test_pattern)
    redis_mock.scan.assert_called_with(0, match="cache:test:*")
    redis_mock.delete.assert_called()

@pytest.mark.asyncio
async def test_cache_increment(redis_client, redis_mock):
    """Test increment operations."""
    redis_mock.incrby.return_value = 5
    result = await redis_client.incrby("counter")
    assert result == 5
    redis_mock.incrby.assert_called_with("cache:counter", 1)

@pytest.mark.asyncio
async def test_cache_pipeline(redis_client, redis_mock):
    """Test pipeline operations."""
    pipeline = await redis_client.pipeline()
    await pipeline.set("key1", "value1")
    await pipeline.set("key2", "value2")
    await pipeline.get("counter")
    
    results = await pipeline.execute()
    assert results[2] == "5"

@pytest.mark.asyncio
async def test_cache_error_handling(redis_client, redis_mock):
    """Test error handling for cache operations."""
    # Simulate error conditions
    redis_mock.get.side_effect = Exception("Redis error")
    result = await redis_client.get("error_key")
    assert result is None

@pytest.mark.asyncio
async def test_cache_performance(redis_client, redis_mock):
    """Test cache performance metrics."""
    # Test multiple operations
    for i in range(10):
        await redis_client.set(f"perf_key_{i}", f"value_{i}")
    assert redis_mock.set.call_count == 10 