"""Rate limiting middleware."""

from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings
from core.utils.logger import get_logger
from core.utils.redis import RateLimit
from core.exceptions.base_exceptions import RateLimitError

logger = get_logger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    def __init__(
        self,
        app: ASGIApp,
        redis_client,
        limit: int = settings.RATE_LIMIT_PER_MINUTE,
        window: int = 60,
        exclude_paths: Optional[list[str]] = None,
        key_func: Optional[Callable] = None
    ):
        """Initialize rate limit middleware.
        
        Args:
            app: ASGI application
            redis_client: Redis client instance
            limit: Maximum number of requests per window
            window: Time window in seconds
            exclude_paths: List of paths to exclude from rate limiting
            key_func: Optional function to generate rate limit key
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.limit = limit
        self.window = window
        self.exclude_paths = exclude_paths or []
        self.key_func = key_func or self._default_key_func

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request through rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response from next middleware/handler
            
        Raises:
            RateLimitError: If rate limit is exceeded
        """
        if await self._should_skip(request):
            return await call_next(request)

        key = await self.key_func(request)
        rate_limiter = RateLimit(
            redis=self.redis_client,
            key=key,
            limit=self.limit,
            window=self.window
        )

        try:
            await rate_limiter.check_limit()
            response = await call_next(request)
            
            # Increment after successful request
            current = await rate_limiter.increment()
            remaining = max(0, self.limit - current)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(
                int((await rate_limiter.get_reset_time()).timestamp())
            )
            
            return response

        except RateLimitError as e:
            logger.warning(
                f"Rate limit exceeded for {key}",
                extra={
                    "key": key,
                    "limit": self.limit,
                    "window": self.window
                }
            )
            raise e

        except Exception as e:
            logger.error(
                f"Error in rate limit middleware: {str(e)}",
                extra={
                    "key": key,
                    "limit": self.limit,
                    "window": self.window
                }
            )
            # Continue processing on error
            return await call_next(request)

    async def _should_skip(self, request: Request) -> bool:
        """Check if rate limiting should be skipped.
        
        Args:
            request: FastAPI request
            
        Returns:
            True if rate limiting should be skipped
        """
        path = request.url.path
        return any(
            path.startswith(exclude_path)
            for exclude_path in self.exclude_paths
        )

    async def _default_key_func(self, request: Request) -> str:
        """Generate default rate limit key from request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Rate limit key string
        """
        # Get client IP, falling back to a default if not found
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
            
        return f"{ip}:{request.url.path}" 