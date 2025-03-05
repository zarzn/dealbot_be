"""Tests for the Redis service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from core.services.redis import RedisService, get_redis_service

@pytest.fixture
async def redis_mock():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=0)
    mock.expire = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.flushdb = AsyncMock(return_value=True)
    mock.close = AsyncMock(return_value=None)
    mock.sadd = AsyncMock(return_value=1)
    mock.srem = AsyncMock(return_value=1)
    mock.smembers = AsyncMock(return_value=set())
    mock.hset = AsyncMock(return_value=True)
    mock.hget = AsyncMock(return_value=None)
    mock.hgetall = AsyncMock(return_value={})
    mock.hdel = AsyncMock(return_value=1)
    mock.pipeline.return_value.__aenter__.return_value = mock
    mock.pipeline.return_value.__aexit__.return_value = None
    mock.pipeline.return_value.execute = AsyncMock(return_value=[])
    return mock

@pytest.fixture
async def redis_service(redis_mock):
    """Get Redis service with mock Redis client."""
    with patch('core.services.redis.RedisService._get_pool', return_value=AsyncMock()):
        with patch('core.services.redis.Redis', return_value=redis_mock):
            service = RedisService()
            await service.init(client=redis_mock)
            yield service
            await service.close()

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_service_initialization():
    """Test Redis service initialization."""
    with patch('core.services.redis.RedisService._get_pool', 
              return_value=AsyncMock()) as mock_get_pool:
        with patch('core.services.redis.Redis', 
                  return_value=AsyncMock()) as mock_redis:
            
            # Test service initialization
            service = RedisService()
            await service.init()
            assert service._client is not None
            mock_get_pool.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.service
async def test_get_redis_service():
    """Test get_redis_service factory function."""
    with patch('core.services.redis.RedisService', new_callable=MagicMock) as mock_redis_service:
        # Set up the mock
        mock_instance = MagicMock()
        mock_redis_service.return_value = mock_instance
        
        # Test the factory function
        service1 = await get_redis_service()
        service2 = await get_redis_service()
        
        # Should return the same instance (singleton)
        assert service1 == service2
        mock_redis_service.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_set_get(redis_service, redis_mock):
    """Test setting and getting values from Redis."""
    # Setup
    key = "test_key"
    value = {"name": "Test Name", "value": 123}
    
    # Test set
    await redis_service.set(key, value)
    redis_mock.set.assert_called_once_with(
        key, 
        json.dumps(value), 
        ex=None
    )
    
    # Setup mock for get
    redis_mock.get.return_value = json.dumps(value)
    
    # Test get
    result = await redis_service.get(key)
    assert result == value
    redis_mock.get.assert_called_once_with(key)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_delete(redis_service, redis_mock):
    """Test deleting values from Redis."""
    # Setup
    key = "test_key"
    
    # Test delete
    await redis_service.delete(key)
    redis_mock.delete.assert_called_once_with(key)
    
    # Test delete multiple keys
    keys = ["key1", "key2", "key3"]
    await redis_service.delete(*keys)
    redis_mock.delete.assert_called_with(*keys)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_exists(redis_service, redis_mock):
    """Test checking if keys exist in Redis."""
    # Setup
    key = "test_key"
    
    # Test when key doesn't exist
    redis_mock.exists.return_value = 0
    exists = await redis_service.exists(key)
    assert not exists
    redis_mock.exists.assert_called_with(key)
    
    # Test when key exists
    redis_mock.exists.return_value = 1
    exists = await redis_service.exists(key)
    assert exists
    redis_mock.exists.assert_called_with(key)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_expire(redis_service, redis_mock):
    """Test setting expiration on keys."""
    # Setup
    key = "test_key"
    seconds = a = 60
    
    # Test expire
    await redis_service.expire(key, seconds)
    redis_mock.expire.assert_called_once_with(key, seconds)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_setex(redis_service, redis_mock):
    """Test setting values with expiration."""
    # Setup
    key = "test_key"
    value = {"name": "Test Name", "value": 123}
    seconds = 60
    
    # Test setex
    await redis_service.setex(key, seconds, value)
    redis_mock.setex.assert_called_once_with(
        key, 
        seconds,
        json.dumps(value)
    )

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_token_blacklisting(redis_service, redis_mock):
    """Test token blacklisting functionality."""
    # Setup
    token = "test_token_123"
    expires_delta = 60
    
    # Test blacklisting a token
    await redis_service.blacklist_token(token, expires_delta)
    redis_mock.setex.assert_called_once_with(
        f"blacklist:{token}", 
        expires_delta,
        "1"
    )
    
    # Test checking if token is blacklisted
    redis_mock.exists.return_value = 0
    is_blacklisted = await redis_service.is_token_blacklisted(token)
    assert not is_blacklisted
    redis_mock.exists.assert_called_with(f"blacklist:{token}")
    
    # Test with blacklisted token
    redis_mock.exists.return_value = 1
    is_blacklisted = await redis_service.is_token_blacklisted(token)
    assert is_blacklisted
    redis_mock.exists.assert_called_with(f"blacklist:{token}")

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_hash_operations(redis_service, redis_mock):
    """Test Redis hash operations."""
    # Setup
    hash_key = "user:123"
    field = "profile"
    value = {"name": "Test User", "email": "test@example.com"}
    
    # Test hset
    await redis_service.hset(hash_key, field, value)
    redis_mock.hset.assert_called_once_with(
        hash_key, 
        field,
        json.dumps(value)
    )
    
    # Setup mock for hget
    redis_mock.hget.return_value = json.dumps(value)
    
    # Test hget
    result = await redis_service.hget(hash_key, field)
    assert result == value
    redis_mock.hget.assert_called_once_with(hash_key, field)
    
    # Setup mock for hgetall
    redis_mock.hgetall.return_value = {
        "profile": json.dumps(value),
        "status": json.dumps("active")
    }
    
    # Test hgetall
    result = await redis_service.hgetall(hash_key)
    assert result == {
        "profile": value,
        "status": "active"
    }
    redis_mock.hgetall.assert_called_once_with(hash_key)
    
    # Test hdel
    await redis_service.hdel(hash_key, field)
    redis_mock.hdel.assert_called_once_with(hash_key, field)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_set_operations(redis_service, redis_mock):
    """Test Redis set operations."""
    # Setup
    set_key = "user:123:roles"
    member = "admin"
    
    # Test sadd
    await redis_service.sadd(set_key, member)
    redis_mock.sadd.assert_called_once_with(set_key, member)
    
    # Test sadd multiple members
    members = ["user", "moderator", "admin"]
    await redis_service.sadd(set_key, *members)
    redis_mock.sadd.assert_called_with(set_key, *members)
    
    # Setup mock for smembers
    redis_mock.smembers.return_value = {"admin", "user", "moderator"}
    
    # Test smembers
    result = await redis_service.smembers(set_key)
    assert result == {"admin", "user", "moderator"}
    redis_mock.smembers.assert_called_once_with(set_key)
    
    # Test srem
    await redis_service.srem(set_key, member)
    redis_mock.srem.assert_called_once_with(set_key, member)
    
    # Test srem multiple members
    members = ["user", "moderator"]
    await redis_service.srem(set_key, *members)
    redis_mock.srem.assert_called_with(set_key, *members)

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_error_handling(redis_service, redis_mock):
    """Test error handling in Redis operations."""
    # Setup
    key = "test_key"
    value = {"name": "Test Name", "value": 123}
    
    # Test handling connection errors
    redis_mock.set.side_effect = Exception("Connection error")
    
    # Should not raise exception but log the error
    await redis_service.set(key, value)
    
    # Test other operations with errors
    redis_mock.get.side_effect = Exception("Connection error")
    result = await redis_service.get(key)
    assert result is None

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_flush_db(redis_service, redis_mock):
    """Test flushing the Redis database."""
    # Test flush
    await redis_service.flush_db()
    redis_mock.flushdb.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.service
async def test_redis_close(redis_service, redis_mock):
    """Test closing the Redis connection."""
    # Test close
    await redis_service.close()
    redis_mock.close.assert_called_once() 