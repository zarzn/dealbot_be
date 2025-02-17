"""Middleware initialization and configuration."""

from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthMiddleware
from .rate_limit import RateLimitMiddleware
from .performance import PerformanceMiddleware
from .logging import RequestLoggingMiddleware
from core.config import settings
from core.utils.metrics import MetricsManager
from core.utils.redis import get_redis_client

__all__ = [
    "AuthMiddleware",
    "RateLimitMiddleware",
    "PerformanceMiddleware",
    "RequestLoggingMiddleware",
    "setup_middleware"
]

async def setup_middleware(app: FastAPI) -> None:
    """Configure and add middleware to the FastAPI application.
    
    The order of middleware is important:
    1. CORS (outermost) - To handle preflight requests before other middleware
    2. Request Logging - To log all requests including those rejected by other middleware
    3. Performance Monitoring - To track performance including auth and rate limiting overhead
    4. Rate Limiting - To prevent abuse before processing auth
    5. Authentication (innermost) - To authenticate requests that passed rate limiting
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
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
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
    
    # Performance Monitoring Middleware
    app.add_middleware(
        PerformanceMiddleware,
        metrics_manager=metrics_manager,
        slow_request_threshold=settings.SLOW_REQUEST_THRESHOLD
    )
    
    # Rate Limiting Middleware
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window=60,  # 1 minute window
        exclude_paths=settings.AUTH_EXCLUDE_PATHS
    )
    
    # Authentication Middleware
    app.add_middleware(
        AuthMiddleware,
        exclude_paths=settings.AUTH_EXCLUDE_PATHS
    ) 