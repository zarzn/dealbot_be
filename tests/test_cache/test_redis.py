"""Test Redis cache operations.

This module contains test cases for Redis cache operations using a mock Redis implementation.
"""

# Standard library imports
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict

# Core imports
from core.utils.redis import RedisClient, RateLimit
from core.exceptions.base_exceptions import RateLimitError

# Test imports
from tests.mocks.redis_mock import RedisMock

@pytest.fixture
async def redis_mock():
    """Provide Redis mock instance."""
    mock = RedisMock()
    yield mock
    await mock.close()

@pytest.fixture
async def redis_client(redis_mock):
    """Provide Redis client with mock."""
    client = RedisClient()
    client._client = redis_mock
    return client

@pytest.mark.asyncio
async def test_basic_cache_operations(redis_client):
    """Test basic set, get, and delete operations."""
    client = await redis_client
    
    # Test set and get
    key = "test_key"
    value = {"name": "test", "value": 123}
    
    assert await client.set(key, value)
    result = await client.get(key)
    assert result == value
    
    # Test delete
    assert await client.delete(key)
    assert await client.get(key) is None

@pytest.mark.asyncio
async def test_cache_with_ttl(redis_client):
    """Test cache operations with TTL."""
    client = await redis_client
    
    key = "ttl_key"
    value = "test_value"
    ttl = 2  # 2 seconds
    
    await client.set(key, value, expire=ttl)
    assert await client.get(key) == value
    
    # Wait for expiration
    await asyncio.sleep(ttl + 1)
    assert await client.get(key) is None

@pytest.mark.asyncio
async def test_cache_complex_data(redis_client):
    """Test caching complex data structures."""
    client = await redis_client
    
    key = "complex_key"
    value = {
        "string": "test",
        "number": 123,
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": 2},
        "boolean": True,
        "null": None,
        "datetime": datetime.now().isoformat()
    }
    
    assert await client.set(key, value)
    result = await client.get(key)
    assert result == value

@pytest.mark.asyncio
async def test_cache_pattern_operations(redis_client):
    """Test clearing cache by key patterns."""
    client = await redis_client
    
    # Set multiple keys
    keys = ["test:1", "test:2", "other:1"]
    for key in keys:
        await client.set(key, "value")
    
    # Clear test:* pattern
    assert await client.clear_pattern("test:*")
    
    # Verify test:* keys are cleared
    assert await client.get("test:1") is None
    assert await client.get("test:2") is None
    assert await client.get("other:1") is not None

@pytest.mark.asyncio
async def test_cache_increment(redis_client):
    """Test increment operations."""
    client = await redis_client
    
    key = "counter"
    
    # Test initial increment
    assert await client.incrby(key) == 1
    
    # Test increment by specific amount
    assert await client.incrby(key, 5) == 6
    
    # Test multiple increments
    assert await client.incrby(key) == 7
    assert await client.incrby(key, 3) == 10

@pytest.mark.asyncio
async def test_rate_limiting(redis_mock):
    """Test rate limiting functionality."""
    from core.utils.redis import RateLimit
    
    # Configure rate limit
    limit = 5
    window = 10
    key = "rate_limit_test"
    
    rate_limiter = RateLimit(redis_mock, key, limit, window)
    
    # Test within limit
    for _ in range(limit):
        assert await rate_limiter.is_allowed()
        await rate_limiter.increment()
    
    # Test exceeding limit
    assert not await rate_limiter.is_allowed()
    with pytest.raises(RateLimitError):
        await rate_limiter.check_limit()

@pytest.mark.asyncio
async def test_cache_pipeline(redis_client):
    """Test pipeline operations."""
    client = await redis_client
    pipeline = client._client.pipeline()
    
    # Queue multiple operations
    await pipeline.set("key1", "value1")
    await pipeline.set("key2", "value2")
    await pipeline.incrby("counter", 5)
    
    # Execute pipeline
    results = await pipeline.execute()
    assert all(results)  # All operations should succeed
    
    # Verify results
    assert await client.get("key1") == "value1"
    assert await client.get("key2") == "value2"
    assert await client.get("counter") == 5

@pytest.mark.asyncio
async def test_cache_error_handling(redis_client):
    """Test error handling for cache operations."""
    client = await redis_client
    
    # Test non-existent key
    assert await client.get("nonexistent") is None
    
    # Test delete non-existent key
    assert await client.delete("nonexistent")
    
    # Test clear non-existent pattern
    assert await client.clear_pattern("nonexistent:*")

@pytest.mark.asyncio
async def test_cache_performance(redis_client):
    """Test cache performance metrics."""
    client = await redis_client
    
    key = "perf_test"
    value = "test_value"
    iterations = 100
    
    # Measure set performance
    start_time = datetime.now()
    for i in range(iterations):
        await client.set(f"{key}:{i}", value)
    set_duration = (datetime.now() - start_time).total_seconds()
    
    # Measure get performance
    start_time = datetime.now()
    for i in range(iterations):
        await client.get(f"{key}:{i}")
    get_duration = (datetime.now() - start_time).total_seconds()
    
    # Assert reasonable performance
    assert set_duration < 1.0  # Less than 1 second for 100 operations
    assert get_duration < 1.0

@pytest.mark.asyncio
async def test_cache_cleanup(redis_client):
    """Test cleanup of expired cache entries."""
    client = await redis_client
    
    # Set multiple keys with different TTLs
    await client.set("short_ttl", "value1", expire=1)
    await client.set("long_ttl", "value2", expire=10)
    await client.set("no_ttl", "value3")
    
    # Wait for short TTL to expire
    await asyncio.sleep(2)
    
    # Verify expired key is cleaned up
    assert await client.get("short_ttl") is None
    assert await client.get("long_ttl") == "value2"
    assert await client.get("no_ttl") == "value3" 