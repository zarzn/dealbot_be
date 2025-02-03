"""Redis rate limiter utility.

This module provides a Redis-based rate limiting implementation for API requests.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError, RateLimitExceeded
from ..config import settings

logger = logging.getLogger(__name__)

class RedisRateLimiter:
    """Asynchronous Redis-based rate limiter."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "ratelimit",
        limit: int = 100,  # 100 requests
        window: int = 3600,  # 1 hour
        precision: int = 60  # 1 minute precision
    ):
        """Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance
            prefix: Rate limit key prefix
            limit: Maximum requests per window
            window: Time window in seconds
            precision: Time precision in seconds
        """
        self.redis = redis_client
        self.prefix = prefix
        self.limit = limit
        self.window = window
        self.precision = precision

    def _make_key(self, identifier: str) -> str:
        """Create rate limit key.
        
        Args:
            identifier: Rate limit identifier
            
        Returns:
            Rate limit key
        """
        return f"{self.prefix}:{identifier}"

    async def get_limit_data(
        self,
        identifier: str
    ) -> Dict[str, Any]:
        """Get current rate limit data.
        
        Args:
            identifier: Rate limit identifier
            
        Returns:
            Rate limit data including remaining requests and reset time
            
        Raises:
            CacheOperationError: If data retrieval fails
        """
        try:
            key = self._make_key(identifier)
            now = int(time.time())
            window_start = now - (now % self.window)
            
            # Get current count
            count = 0
            async with self.redis.pipeline() as pipe:
                # Get all counts in current window
                for ts in range(window_start, now, self.precision):
                    count_key = f"{key}:{ts}"
                    pipe.get(count_key)
                    
                counts = await pipe.execute()
                count = sum(int(c) for c in counts if c)
            
            return {
                "limit": self.limit,
                "remaining": max(0, self.limit - count),
                "reset": window_start + self.window,
                "window": self.window
            }
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get rate limit data",
                details={"identifier": identifier, "error": str(e)}
            )

    async def check_rate_limit(
        self,
        identifier: str
    ) -> Dict[str, Any]:
        """Check if rate limit is exceeded.
        
        Args:
            identifier: Rate limit identifier
            
        Returns:
            Rate limit data
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
            CacheOperationError: If check fails
        """
        limit_data = await self.get_limit_data(identifier)
        
        if limit_data["remaining"] <= 0:
            raise RateLimitExceeded(
                message="Rate limit exceeded",
                details={
                    "identifier": identifier,
                    "limit": limit_data["limit"],
                    "reset": limit_data["reset"]
                }
            )
            
        return limit_data

    async def record_request(
        self,
        identifier: str,
        count: int = 1
    ) -> Dict[str, Any]:
        """Record API request.
        
        Args:
            identifier: Rate limit identifier
            count: Number of requests to record
            
        Returns:
            Updated rate limit data
            
        Raises:
            CacheOperationError: If recording fails
        """
        try:
            key = self._make_key(identifier)
            now = int(time.time())
            bucket = now - (now % self.precision)
            count_key = f"{key}:{bucket}"
            
            # Increment count in current bucket
            async with self.redis.pipeline() as pipe:
                pipe.incrby(count_key, count)
                pipe.expire(count_key, self.window)
                await pipe.execute()
                
            return await self.get_limit_data(identifier)
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to record request",
                details={"identifier": identifier, "error": str(e)}
            )

    async def reset_limit(
        self,
        identifier: str
    ) -> None:
        """Reset rate limit.
        
        Args:
            identifier: Rate limit identifier
            
        Raises:
            CacheOperationError: If reset fails
        """
        try:
            key = self._make_key(identifier)
            pattern = f"{key}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.redis.delete(*keys)
                    
                if cursor == 0:
                    break
                    
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to reset rate limit",
                details={"identifier": identifier, "error": str(e)}
            )

class RateLimitManager:
    """Manager for creating rate limiters."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        default_limit: int = 100,
        default_window: int = 3600,
        default_precision: int = 60
    ):
        """Initialize rate limit manager.
        
        Args:
            redis_client: Redis client instance
            default_limit: Default request limit
            default_window: Default time window in seconds
            default_precision: Default time precision in seconds
        """
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
        self.default_precision = default_precision
        self._limiters: Dict[str, RedisRateLimiter] = {}

    def get_rate_limiter(
        self,
        prefix: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        precision: Optional[int] = None
    ) -> RedisRateLimiter:
        """Get or create rate limiter.
        
        Args:
            prefix: Rate limiter prefix
            limit: Optional request limit
            window: Optional time window in seconds
            precision: Optional time precision in seconds
            
        Returns:
            RedisRateLimiter instance
        """
        if prefix not in self._limiters:
            self._limiters[prefix] = RedisRateLimiter(
                redis_client=self.redis,
                prefix=prefix,
                limit=limit or self.default_limit,
                window=window or self.default_window,
                precision=precision or self.default_precision
            )
        return self._limiters[prefix] 