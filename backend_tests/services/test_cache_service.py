"""Cache service tests."""

import pytest
import json
import asyncio
from datetime import timedelta
from core.services.cache import CacheService
from core.exceptions import CacheError

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def cache_service(redis_client):
    """Create cache service for tests."""
    return CacheService(redis_client)

@pytest.mark.service
async def test_set_get_cache(cache_service):
    """Test setting and getting cached values."""
    key = "test_key"
    value = "test_value"
    
    # Set value in cache
    await cache_service.set(key, value)
    
    # Get value from cache
    cached_value = await cache_service.get(key)
    assert cached_value == value

@pytest.mark.service
async def test_cache_expiration(cache_service):
    """Test cache expiration."""
    key = "expiring_key"
    value = "test_value"
    expire = timedelta(seconds=1)
    
    # Set value with expiration
    await cache_service.set(key, value, expire=expire)
    
    # Value should exist initially
    assert await cache_service.exists(key)
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    
    # Value should be gone
    assert not await cache_service.exists(key)
    assert await cache_service.get(key) is None

@pytest.mark.service
async def test_delete_cache(cache_service):
    """Test deleting cached values."""
    key = "delete_key"
    value = "test_value"
    
    # Set value
    await cache_service.set(key, value)
    assert await cache_service.exists(key)
    
    # Delete value
    await cache_service.delete(key)
    assert not await cache_service.exists(key)
    assert await cache_service.get(key) is None

@pytest.mark.service
async def test_clear_pattern(cache_service):
    """Test clearing cache by pattern."""
    # Set multiple values
    await cache_service.set("test:1", "value1")
    await cache_service.set("test:2", "value2")
    await cache_service.set("other:1", "value3")
    
    # Clear by pattern
    await cache_service.clear_pattern("test:*")
    
    # Verify test:* keys are gone
    assert not await cache_service.exists("test:1")
    assert not await cache_service.exists("test:2")
    
    # Verify other keys remain
    assert await cache_service.exists("other:1")

@pytest.mark.service
async def test_increment(cache_service):
    """Test incrementing cached values."""
    key = "counter"
    
    # Initial increment
    value = await cache_service.incrby(key)
    assert value == 1
    
    # Increment by specific amount
    value = await cache_service.incrby(key, 5)
    assert value == 6
    
    # Verify final value
    assert await cache_service.get(key) == 6

@pytest.mark.service
async def test_complex_data_types(cache_service):
    """Test caching complex data types."""
    key = "complex_data"
    data = {
        "string": "test",
        "number": 42,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
        "bool": True,
        "null": None
    }
    
    # Set complex data
    await cache_service.set(key, data)
    
    # Get and verify data
    cached_data = await cache_service.get(key)
    assert cached_data == data
    assert isinstance(cached_data["list"], list)
    assert isinstance(cached_data["dict"], dict)

@pytest.mark.service
async def test_cache_pipeline(cache_service):
    """Test pipeline operations."""
    # Create multiple operations
    pipeline = await cache_service.pipeline()
    await pipeline.set("key1", "value1")
    await pipeline.set("key2", "value2")
    await pipeline.get("key1")
    await pipeline.get("key2")
    
    # Execute pipeline
    results = await pipeline.execute()
    
    # Verify results
    assert results[0]  # First set operation
    assert results[1]  # Second set operation
    assert results[2] == "value1"  # First get operation
    assert results[3] == "value2"  # Second get operation

@pytest.mark.service
async def test_cache_error_handling(cache_service):
    """Test error handling in cache operations."""
    # Test invalid JSON
    with pytest.raises(CacheError):
        await cache_service.set("invalid", object())
    
    # Test invalid key type
    with pytest.raises(CacheError):
        await cache_service.get(123)  # Non-string key
    
    # Test invalid expiration
    with pytest.raises(CacheError):
        await cache_service.set("key", "value", expire="invalid")

@pytest.mark.service
async def test_cache_connection_handling(cache_service):
    """Test cache connection handling."""
    # Test connection is working
    assert await cache_service.ping()
    
    # Test connection cleanup
    await cache_service.close()
    
    # Test reconnection
    assert await cache_service.ping()

@pytest.mark.service
async def test_cache_prefix_handling(cache_service):
    """Test cache key prefix handling."""
    key = "test_key"
    value = {"data": "test_value"}  # Use a JSON-serializable value
    
    # Set value with default prefix
    await cache_service.set(key, value)
    
    # Value should be retrievable with same key
    assert await cache_service.get(key) == value
    
    # Value should not be retrievable without prefix
    raw_value = await cache_service._client.get(key)
    assert raw_value is None
    
    # Value should be retrievable with full prefixed key
    prefixed_value = await cache_service._client.get(f"{cache_service._prefix}{key}")
    assert json.loads(prefixed_value) == value 