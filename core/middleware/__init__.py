"""Middleware initialization and configuration."""

from typing import List
from fastapi import FastAPI

from .auth import AuthMiddleware
from .rate_limit import RateLimitMiddleware
from .performance import PerformanceMiddleware
from .logging import RequestLoggingMiddleware
from core.config import settings

__all__ = [
    "AuthMiddleware",
    "RateLimitMiddleware",
    "PerformanceMiddleware",
    "RequestLoggingMiddleware",
    "setup_middleware"
]

def setup_middleware(app: FastAPI) -> None:
    """Configure and add middleware to the FastAPI application.
    
    The order of middleware is important:
    1. Request Logging (outermost) - To log all requests including those rejected by other middleware
    2. Performance Monitoring - To track performance including auth and rate limiting overhead
    3. Rate Limiting - To prevent abuse before processing auth
    4. Authentication (innermost) - To authenticate requests that passed rate limiting
    """
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
        slow_request_threshold=settings.SLOW_REQUEST_THRESHOLD,
        log_performance=settings.LOG_PERFORMANCE
    )
    
    # Rate Limiting Middleware
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit_per_second=settings.RATE_LIMIT_PER_SECOND,
        rate_limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
        burst_limit=settings.RATE_LIMIT_BURST
    )
    
    # Authentication Middleware
    app.add_middleware(
        AuthMiddleware,
        exclude_paths=settings.AUTH_EXCLUDE_PATHS
    ) 