"""Middleware components for request processing.

This module provides middleware components for the AI Agentic Deals System,
including request logging, rate limiting, authentication, and performance monitoring.
"""

import time
import uuid
from typing import Callable, Dict, Any, Optional, List
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.datastructures import Headers
from prometheus_client import Counter, Histogram
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import logging

from jose import JWTError, jwt
from core.config import get_settings
from core.utils.logger import get_logger, get_request_logger
from core.utils.redis import RateLimit, RedisClient
from core.exceptions import (
    RateLimitError,
    AuthenticationError,
    TokenExpiredError,
    TokenInvalidError
)
from core.metrics.middleware import MiddlewareMetrics
from core.services.auth import get_current_user
from core.models.user import User

logger = get_logger(__name__)
settings = get_settings()
metrics = MiddlewareMetrics()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request logging with metrics."""

    SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}
    SENSITIVE_FIELDS = {"password", "token", "key", "secret"}

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request and log details with metrics."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request_logger = get_request_logger(logger, request_id)
        
        # Start metrics
        metrics.request_started(request.method, request.url.path)
        start_time = time.time()
        
        try:
            # Log sanitized request details
            await self._log_request(request, request_logger)
            
            # Process request
            response = await call_next(request)
            
            # Log response and update metrics
            process_time = (time.time() - start_time) * 1000
            metrics.request_completed(
                request.method,
                request.url.path,
                response.status_code,
                process_time
            )
            await self._log_response(response, process_time, request_logger)
            
            return response
            
        except Exception as e:
            # Log error and update metrics
            process_time = (time.time() - start_time) * 1000
            metrics.request_failed(
                request.method,
                request.url.path,
                type(e).__name__,
                process_time
            )
            await self._log_error(e, process_time, request_logger)
            raise

    def _sanitize_headers(self, headers: Headers) -> Dict[str, str]:
        """Sanitize sensitive information from headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                sanitized[key] = "***"
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive information from data."""
        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in self.SENSITIVE_FIELDS):
                sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            else:
                sanitized[key] = value
        return sanitized

    async def _log_request(self, request: Request, logger: Any) -> None:
        """Log sanitized request details."""
        # Get request body if available
        body = {}
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
            except Exception:
                body = {"error": "Could not parse request body"}

        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "headers": self._sanitize_headers(request.headers),
                "client": request.client.host if request.client else None,
                "path_params": request.path_params,
                "query_params": dict(request.query_params),
                "body": self._sanitize_data(body)
            }
        )

    async def _log_response(
        self,
        response: Response,
        process_time: float,
        logger: Any
    ) -> None:
        """Log sanitized response details."""
        logger.info(
            "Request completed",
            extra={
                "status_code": response.status_code,
                "process_time_ms": round(process_time, 2),
                "headers": self._sanitize_headers(response.headers),
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length")
            }
        )

    async def _log_error(
        self,
        error: Exception,
        process_time: float,
        logger: Any
    ) -> None:
        """Log detailed error information."""
        logger.error(
            "Request failed",
            extra={
                "error": str(error),
                "error_type": type(error).__name__,
                "error_class": error.__class__.__name__,
                "process_time_ms": round(process_time, 2),
                "traceback": getattr(error, "__traceback__", None)
            },
            exc_info=True
        )

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for advanced rate limiting with burst support."""

    def __init__(
        self,
        app: ASGIApp,
        limit_per_second: int = settings.RATE_LIMIT_PER_SECOND,
        limit_per_minute: int = settings.RATE_LIMIT_PER_MINUTE,
        burst_multiplier: float = settings.RATE_LIMIT_BURST_MULTIPLIER
    ):
        super().__init__(app)
        self.limit_per_second = limit_per_second
        self.limit_per_minute = limit_per_minute
        self.burst_multiplier = burst_multiplier
        self.skip_paths = {
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request with advanced rate limiting."""
        if request.url.path in self.skip_paths:
            return await call_next(request)

        client_id = self._get_client_id(request)
        
        # Check both per-second and per-minute limits
        second_limit = RateLimit(
            key=f"1s:{client_id}",
            limit=self.limit_per_second,
            window=1,
            burst_multiplier=self.burst_multiplier
        )
        
        minute_limit = RateLimit(
            key=f"1m:{client_id}",
            limit=self.limit_per_minute,
            window=60,
            burst_multiplier=self.burst_multiplier
        )
        
        # Check limits
        for rate_limit, window in [(second_limit, "second"), (minute_limit, "minute")]:
            if not await rate_limit.is_allowed():
                remaining = await rate_limit.get_remaining()
                reset_after = await rate_limit.get_reset_time()
                
                metrics.rate_limit_exceeded(client_id, window)
                
                raise RateLimitError(
                    message=f"Rate limit exceeded for {window}",
                    details={
                        "limit": rate_limit.limit,
                        "remaining": remaining,
                        "reset_after": reset_after,
                        "window": window
                    }
                )

        # Update metrics
        metrics.rate_limit_allowed(client_id)
        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier with additional context."""
        identifiers = []
        
        # User ID if authenticated
        if hasattr(request.state, "user_id"):
            identifiers.append(f"user:{request.state.user_id}")
        
        # IP address
        if request.client:
            identifiers.append(f"ip:{request.client.host}")
        
        # API key if present
        api_key = request.headers.get("X-API-Key")
        if api_key:
            identifiers.append(f"api:{api_key}")
        
        return ":".join(identifiers) if identifiers else "anonymous"

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication and authorization."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.skip_paths = {
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request with JWT authentication."""
        if request.url.path in self.skip_paths:
            return await call_next(request)

        try:
            # Get and validate token
            token = self._get_token(request)
            if not token:
                metrics.auth_failed("no_token")
                raise AuthenticationError("No authentication token provided")

            # Validate token and get user info
            user_info = await self._validate_token(token)
            request.state.user = user_info
            request.state.user_id = user_info["id"]
            
            # Update metrics
            metrics.auth_success(user_info["id"])
            
            # Add user context to response headers
            response = await call_next(request)
            response.headers["X-User-ID"] = str(user_info["id"])
            return response
            
        except jwt.ExpiredSignatureError:
            metrics.auth_failed("token_expired")
            raise TokenExpiredError("Authentication token has expired")
        except jwt.InvalidTokenError as e:
            metrics.auth_failed("token_invalid")
            raise TokenInvalidError(f"Invalid authentication token: {str(e)}")
        except Exception as e:
            metrics.auth_failed(type(e).__name__)
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def _get_token(self, request: Request) -> Optional[str]:
        """Get authentication token from various sources."""
        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
            
        # Try cookie
        token = request.cookies.get("access_token")
        if token:
            return token
            
        # Try query parameter (only for WebSocket connections)
        if request.url.path.startswith("/ws"):
            return request.query_params.get("token")
            
        return None

    async def _validate_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token and return user info."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            # Check token expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                raise jwt.ExpiredSignatureError("Token has expired")
                
            return payload
            
        except jwt.ExpiredSignatureError:
            raise
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError(f"Invalid token format: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed performance monitoring."""

    def __init__(
        self,
        app: ASGIApp,
        slow_request_threshold: float = 1000.0  # ms
    ):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request with performance monitoring."""
        start_time = time.time()
        
        # Track memory usage if available
        start_memory = self._get_memory_usage()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate metrics
            process_time = (time.time() - start_time) * 1000
            memory_delta = None
            if start_memory:
                end_memory = self._get_memory_usage()
                memory_delta = end_memory - start_memory
            
            # Update metrics
            metrics.request_duration(
                request.method,
                request.url.path,
                process_time
            )
            
            if memory_delta:
                metrics.memory_usage(
                    request.method,
                    request.url.path,
                    memory_delta
                )
            
            # Add performance headers
            response.headers.update({
                "X-Process-Time": str(round(process_time, 2)),
                "X-Memory-Usage": str(memory_delta) if memory_delta else "N/A"
            })
            
            # Log slow requests
            if process_time > self.slow_request_threshold:
                self._log_slow_request(request, process_time, memory_delta)
            
            return response
            
        except Exception as e:
            # Log performance metrics even for failed requests
            process_time = (time.time() - start_time) * 1000
            metrics.request_duration(
                request.method,
                request.url.path,
                process_time,
                "error"
            )
            raise

    def _get_memory_usage(self) -> Optional[float]:
        """Get current memory usage if available."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return None

    def _log_slow_request(
        self,
        request: Request,
        process_time: float,
        memory_delta: Optional[float]
    ) -> None:
        """Log detailed information about slow requests."""
        logger.warning(
            "Slow request detected",
            extra={
                "method": request.method,
                "path": request.url.path,
                "process_time_ms": round(process_time, 2),
                "memory_delta_mb": round(memory_delta, 2) if memory_delta else None,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "client": request.client.host if request.client else None
            }
        ) 