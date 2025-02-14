"""Request logging middleware."""

import time
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.datastructures import Headers

from core.utils.logger import get_logger, get_request_logger
from core.metrics.middleware import MiddlewareMetrics

logger = get_logger(__name__)
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
        """Process the request and log details."""
        request_id = str(request.state.request_id)
        request_logger = get_request_logger(request_id)
        start_time = time.time()

        try:
            # Log request details
            await self._log_request(request, request_logger)
            
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = (time.time() - start_time) * 1000
            
            # Log response details
            await self._log_response(response, process_time, request_logger)
            
            # Update metrics
            metrics.request_duration.observe(process_time)
            metrics.requests_total.inc()
            
            return response
            
        except Exception as e:
            # Calculate processing time for error
            process_time = (time.time() - start_time) * 1000
            
            # Log error details
            await self._log_error(e, process_time, request_logger)
            
            # Update error metrics
            metrics.request_errors_total.inc()
            
            raise

    def _sanitize_headers(self, headers: Headers) -> Dict[str, str]:
        """Remove sensitive information from headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from request/response data."""
        sanitized = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

    async def _log_request(self, request: Request, logger: Any) -> None:
        """Log request details."""
        headers = self._sanitize_headers(request.headers)
        
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "client_host": request.client.host if request.client else None,
            "path_params": dict(request.path_params),
            "query_params": dict(request.query_params)
        }

        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                log_data["body"] = self._sanitize_data(body)
            except:
                log_data["body"] = "[INVALID JSON]"

        logger.info("Incoming request", extra=log_data)

    async def _log_response(
        self,
        response: Response,
        process_time: float,
        logger: Any
    ) -> None:
        """Log response details."""
        logger.info(
            "Request completed",
            extra={
                "status_code": response.status_code,
                "process_time_ms": process_time,
                "headers": self._sanitize_headers(response.headers)
            }
        )

    async def _log_error(
        self,
        error: Exception,
        process_time: float,
        logger: Any
    ) -> None:
        """Log error details."""
        logger.error(
            "Request failed",
            extra={
                "error": str(error),
                "error_type": error.__class__.__name__,
                "process_time_ms": process_time
            },
            exc_info=True
        ) 