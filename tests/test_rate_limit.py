"""Tests for rate limiting functionality.

This module contains test cases for both the RateLimitMiddleware and the underlying
rate limiting utility functions.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.middleware.rate_limit import RateLimitMiddleware
from core.exceptions import RateLimitError

@pytest.fixture
def test_app(redis_mock):
    """Create test FastAPI app with rate limit middleware."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_mock,
        rate_per_second=1,
        rate_per_minute=2,
        exclude_paths=["/excluded", "/docs"]
    )
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.get("/excluded")
    async def excluded_endpoint():
        return {"message": "success"}
    
    return app

@pytest.fixture
def rate_limiter(redis_mock):
    """Create rate limiter instance for testing."""
    return RateLimitMiddleware(redis_client=redis_mock)

# Middleware Integration Tests
# --------------------------

@pytest.mark.asyncio
async def test_middleware_rate_limit_per_second(test_app, redis_mock):
    """Test rate limiting middleware per second."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        # First request should be allowed
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Second request within the same second should be denied
        response = await client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert "Rate limit exceeded" in data["detail"]["message"]
        assert data["detail"]["limit"] == 1

@pytest.mark.asyncio
async def test_middleware_rate_limit_per_minute(test_app, redis_mock):
    """Test rate limiting middleware per minute."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        # First request should be allowed
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Second request should be allowed
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Third request should be denied
        response = await client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert "Rate limit exceeded" in data["detail"]["message"]
        assert data["detail"]["limit"] == 2

@pytest.mark.asyncio
async def test_middleware_excluded_path(test_app, redis_mock):
    """Test excluded paths bypass rate limiting in middleware."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        # Multiple requests to excluded path should be allowed
        for _ in range(5):
            response = await client.get("/excluded")
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

@pytest.mark.asyncio
async def test_middleware_with_user(test_app, redis_mock):
    """Test rate limiting middleware with authenticated user."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        # Mock user middleware
        @test_app.middleware("http")
        async def mock_user_middleware(request: Request, call_next):
            request.state.user = MagicMock(id="test-user-id")
            return await call_next(request)
        
        # First request should be allowed
        response = await client.get("/test")
        assert response.status_code == 200
        
        # Second request should be denied
        response = await client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert "Rate limit exceeded" in data["detail"]["message"]
        assert data["detail"]["limit"] == 1

# Core Rate Limiter Tests
# ----------------------

@pytest.mark.asyncio
async def test_rate_limit_cleanup(rate_limiter: RateLimitMiddleware, redis_mock):
    """Test cleanup of old rate limit entries."""
    key = "test:rate:limit"
    now = datetime.now().timestamp()
    
    # Add some old entries
    await redis_mock.zadd(key, {
        "old_request1": now - 120,
        "old_request2": now - 90
    })
    
    # Add a recent entry
    await redis_mock.zadd(key, {"recent_request": now - 30})
    
    # Check rate limit which should trigger cleanup
    await rate_limiter._check_rate_limit(redis_mock, key, 5, 60)
    
    # Verify old entries were cleaned up
    count = await redis_mock.zcard(key)
    assert count == 2  # recent_request + new request

@pytest.mark.asyncio
async def test_rate_limit_redis_error(rate_limiter: RateLimitMiddleware, redis_mock):
    """Test handling of Redis errors in rate limiter."""
    key = "test:rate:limit"
    
    # Make pipeline raise an exception
    async def mock_pipeline(*args, **kwargs):
        raise Exception("Redis connection error")
    
    redis_mock.pipeline = mock_pipeline
    
    # Should raise RateLimitError on Redis error
    with pytest.raises(RateLimitError) as exc:
        await rate_limiter._check_rate_limit(redis_mock, key, 5, 60)
    assert "Rate limit check failed" in str(exc.value)
    assert exc.value.limit == 5

@pytest.mark.asyncio
async def test_rate_limit_window_reset(rate_limiter: RateLimitMiddleware, redis_mock):
    """Test rate limit reset after window expires."""
    key = "test:rate:limit"
    
    # Use up all requests
    for _ in range(5):
        await rate_limiter._check_rate_limit(redis_mock, key, 5, 60)
    
    # Next request should be denied
    with pytest.raises(RateLimitError) as exc:
        await rate_limiter._check_rate_limit(redis_mock, key, 5, 60)
    assert "Rate limit exceeded" in str(exc.value)
    
    # Simulate time passing - remove old entries
    now = datetime.now().timestamp()
    await redis_mock.zremrangebyscore(key, 0, now - 61)
    
    # Should be allowed again
    await rate_limiter._check_rate_limit(redis_mock, key, 5, 60)

@pytest.mark.asyncio
async def test_rate_limit_excluded_paths_check(rate_limiter: RateLimitMiddleware):
    """Test that excluded paths check works correctly."""
    # Create a mock request
    request = MagicMock()
    request.url.path = "/excluded"
    
    # Should not check rate limit for excluded path
    assert not await rate_limiter.should_check_rate_limit(request)

@pytest.mark.asyncio
async def test_rate_limit_key_generation(rate_limiter: RateLimitMiddleware):
    """Test rate limit key generation for different user types."""
    # Anonymous user
    anon_request = MagicMock()
    anon_request.client.host = "127.0.0.1"
    anon_request.url.path = "/test"
    anon_key = await rate_limiter._get_rate_limit_key(anon_request)
    assert "ip:" in anon_key
    assert "127.0.0.1" in anon_key
    
    # Authenticated user
    auth_request = MagicMock()
    auth_request.client.host = "127.0.0.1"
    auth_request.url.path = "/test"
    auth_request.state.user = MagicMock(id="test-user-id")
    auth_key = await rate_limiter._get_rate_limit_key(auth_request)
    assert "user:" in auth_key
    assert "test-user-id" in auth_key
    
    # Different users should get different keys
    auth_request2 = MagicMock()
    auth_request2.client.host = "127.0.0.1"
    auth_request2.url.path = "/test"
    auth_request2.state.user = MagicMock(id="other-user-id")
    auth_key2 = await rate_limiter._get_rate_limit_key(auth_request2)
    assert auth_key != auth_key2 