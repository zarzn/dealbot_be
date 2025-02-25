"""Rate limiting middleware.

This module provides rate limiting functionality using Redis as a backend.
"""

from typing import Optional, Callable, List
from fastapi import Request, HTTPException, status
import time
from datetime import datetime
import logging
from redis.asyncio import Redis
from core.services.redis import get_redis_service

from core.config import settings
from core.exceptions import RateLimitError

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    """Rate limiter middleware implementation."""

    def __init__(
        self,
        app: Optional[Callable] = None,
        rate_per_second: Optional[int] = None,
        rate_per_minute: Optional[int] = None,
        exclude_paths: Optional[List[str]] = None
    ):
        """Initialize rate limiter middleware.
        
        Args:
            app: ASGI application
            rate_per_second: Maximum requests per second
            rate_per_minute: Maximum requests per minute
            exclude_paths: Paths to exclude from rate limiting
        """
        self.app = app
        self.rate_per_second = rate_per_second or int(settings.RATE_LIMIT_PER_SECOND)
        self.rate_per_minute = rate_per_minute or int(settings.RATE_LIMIT_PER_MINUTE)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/metrics"
        ]

    async def should_check_rate_limit(self, request: Request) -> bool:
        """Check if request should be rate limited.
        
        Args:
            request: FastAPI request
            
        Returns:
            bool: True if request should be rate limited
        """
        path = request.url.path
        return not any(path.startswith(excluded) for excluded in self.exclude_paths)

    async def _get_rate_limit_key(self, request: Request) -> str:
        """Get rate limit key for request."""
        # Use client IP or user ID if authenticated
        identifier = request.client.host
        if hasattr(request.state, "user") and request.state.user:
            identifier = str(request.state.user.id)
        return f"rate_limit:{identifier}"

    async def _check_rate_limit(
        self,
        redis: Redis,
        key: str,
        limit: int,
        window: int
    ) -> bool:
        """Check if request is within rate limit.
        
        Args:
            redis: Redis client
            key: Redis key
            limit: Maximum requests
            window: Time window in seconds
            
        Returns:
            bool: True if within limit, False otherwise
            
        Raises:
            RateLimitError: If rate limit is exceeded or Redis fails
        """
        try:
            async with redis.pipeline() as pipe:
                now = time.time()
                # Remove old entries
                await pipe.zremrangebyscore(key, 0, now - window)
                # Count current requests
                await pipe.zcard(key)
                # Add new request
                await pipe.zadd(key, {str(now): now})
                # Set expiration
                await pipe.expire(key, window)
                # Execute pipeline
                results = await pipe.execute()
                
                # Get count from results
                count = results[1] if results else 0
                if count >= limit:
                    raise RateLimitError(
                        message=f"Rate limit exceeded: {limit} requests per {window} seconds",
                        limit=limit,
                        reset_at=datetime.fromtimestamp(now + window)
                    )
                return True
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # On Redis error, enforce rate limit to be safe
            raise RateLimitError(
                message="Rate limit check failed",
                limit=limit,
                reset_at=datetime.fromtimestamp(time.time() + window)
            )

    async def __call__(self, scope, receive, send):
        """Rate limiting middleware."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        
        # Skip rate limiting for excluded paths
        if not await self.should_check_rate_limit(request):
            return await self.app(scope, receive, send)

        try:
            redis = await get_redis_service()
            key = await self._get_rate_limit_key(request)
            
            # Check per-second rate limit
            await self._check_rate_limit(redis, f"{key}:second", self.rate_per_second, 1)
                
            # Check per-minute rate limit
            await self._check_rate_limit(redis, f"{key}:minute", self.rate_per_minute, 60)

            return await self.app(scope, receive, send)

        except RateLimitError as e:
            # Convert RateLimitError to HTTP response
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            content = {
                "detail": {
                    "message": str(e),
                    "limit": e.limit,
                    "reset_at": e.reset_at.isoformat() if e.reset_at else None
                }
            }
            
            async def send_error_response(message):
                if message["type"] == "http.response.start":
                    await send({
                        "type": "http.response.start",
                        "status": status_code,
                        "headers": [
                            (b"content-type", b"application/json")
                        ]
                    })
                elif message["type"] == "http.response.body":
                    import json
                    body = json.dumps(content).encode("utf-8")
                    await send({
                        "type": "http.response.body",
                        "body": body,
                        "more_body": False
                    })
            
            await send_error_response({"type": "http.response.start"})
            await send_error_response({"type": "http.response.body"})
            return
            
        except Exception as e:
            logger.error(f"Rate limiting error: {str(e)}")
            # On any error, enforce rate limit to be safe
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            content = {
                "detail": {
                    "message": "Rate limit check failed",
                    "limit": self.rate_per_second,  # Use per-second limit as default
                    "reset_at": datetime.fromtimestamp(time.time() + 1).isoformat()
                }
            }
            
            async def send_error_response(message):
                if message["type"] == "http.response.start":
                    await send({
                        "type": "http.response.start",
                        "status": status_code,
                        "headers": [
                            (b"content-type", b"application/json")
                        ]
                    })
                elif message["type"] == "http.response.body":
                    import json
                    body = json.dumps(content).encode("utf-8")
                    await send({
                        "type": "http.response.body",
                        "body": body,
                        "more_body": False
                    })
            
            await send_error_response({"type": "http.response.start"})
            await send_error_response({"type": "http.response.body"})
            return 