"""Middleware initialization and configuration."""

from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .auth import AuthMiddleware
from .rate_limit import RateLimitMiddleware
from .performance import PerformanceMiddleware
from .logging import RequestLoggingMiddleware
from .error_handler import ErrorHandlerMiddleware
from core.config import settings
from core.utils.metrics import MetricsManager
from core.utils.redis import get_redis_client

__all__ = [
    "AuthMiddleware",
    "RateLimitMiddleware",
    "PerformanceMiddleware",
    "RequestLoggingMiddleware",
    "ErrorHandlerMiddleware",
    "setup_middleware"
]

async def setup_middleware(app: FastAPI) -> None:
    """Configure and add middleware to the FastAPI application.
    
    The order of middleware is important:
    1. CORS (outermost) - To handle preflight requests before other middleware
    2. Request Logging - To log all requests including those rejected by other middleware
    3. Error Handler - To catch and handle errors, providing better error responses
    4. Performance Monitoring - To track performance including auth and rate limiting overhead
    5. Rate Limiting - To prevent abuse before processing auth
    6. Authentication (innermost) - To authenticate requests that passed rate limiting
    """
    # Initialize metrics manager
    metrics_manager = MetricsManager()

    # Get Redis client
    redis_client = await get_redis_client()

    # Add CORS middleware first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token", "X-Requested-With"],
        expose_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token", "X-Requested-With"],
        max_age=600  # 10 minutes
    )

    # Request Logging Middleware
    app.add_middleware(
        RequestLoggingMiddleware,
        sensitive_headers=settings.SENSITIVE_HEADERS,
        sensitive_fields=settings.SENSITIVE_FIELDS,
        exclude_paths=settings.LOG_EXCLUDE_PATHS,
        log_request_body=settings.LOG_REQUEST_BODY,
        log_response_body=settings.LOG_RESPONSE_BODY,
        log_headers=settings.LOG_HEADERS,
        log_query_params=settings.LOG_QUERY_PARAMS
    )
    
    # Error Handler Middleware - after logging, before performance monitoring
    app.add_middleware(ErrorHandlerMiddleware)
    
    # Performance Monitoring Middleware
    app.add_middleware(
        PerformanceMiddleware,
        metrics_manager=metrics_manager,
        slow_request_threshold=settings.SLOW_REQUEST_THRESHOLD
    )
    
    # Rate Limiting Middleware
    app.add_middleware(
        RateLimitMiddleware,
        rate_per_second=int(settings.RATE_LIMIT_PER_SECOND),
        rate_per_minute=int(settings.RATE_LIMIT_PER_MINUTE),
        exclude_paths=settings.AUTH_EXCLUDE_PATHS
    )
    
    # Authentication Middleware
    app.add_middleware(
        AuthMiddleware,
        exclude_paths=settings.AUTH_EXCLUDE_PATHS
    )

    # Add compression middleware
    app.add_middleware(
        GZipMiddleware,
        minimum_size=settings.COMPRESSION_MINIMUM_SIZE
    ) 