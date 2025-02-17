"""Request logging middleware."""

import json
import time
from typing import Callable, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.utils.logger import get_logger

logger = get_logger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request and response details."""

    def __init__(
        self,
        app: ASGIApp,
        sensitive_headers: Set[str] = None,
        sensitive_fields: Set[str] = None,
        exclude_paths: Set[str] = None,
        log_request_body: bool = True,
        log_response_body: bool = False,
        log_headers: bool = True,
        log_query_params: bool = True
    ):
        super().__init__(app)
        # Import settings here to avoid circular imports
        from core.config import settings
        self.sensitive_headers = {h.lower() for h in (sensitive_headers or settings.SENSITIVE_HEADERS)}
        self.sensitive_fields = sensitive_fields or settings.SENSITIVE_FIELDS
        self.exclude_paths = exclude_paths or settings.LOGGING_EXCLUDE_PATHS
        self.log_request_body = log_request_body if log_request_body is not None else settings.LOG_REQUEST_BODY
        self.log_response_body = log_response_body if log_response_body is not None else settings.LOG_RESPONSE_BODY
        self.log_headers = log_headers if log_headers is not None else settings.LOG_HEADERS
        self.log_query_params = log_query_params if log_query_params is not None else settings.LOG_QUERY_PARAMS

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request with logging."""
        # Skip logging for excluded paths
        if self._should_skip_logging(request):
            return await call_next(request)

        start_time = time.time()
        request_id = self._generate_request_id()
        
        # Log request
        await self._log_request(request, request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log response
            duration = time.time() - start_time
            await self._log_response(response, request_id, duration)
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            await self._log_error(e, request_id, duration)
            raise

    async def _log_request(
        self,
        request: Request,
        request_id: str
    ):
        """Log request details."""
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }

        if self.log_query_params:
            log_data["query_params"] = dict(request.query_params)
            
        if self.log_headers:
            log_data["headers"] = self._sanitize_headers(dict(request.headers))
            
        log_data["client_ip"] = self._get_client_ip(request)

        if self.log_request_body and request.method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.json()
                log_data["body"] = self._sanitize_data(body)
            except:
                log_data["body"] = "Could not parse request body"

        logger.info(f"Incoming request: {json.dumps(log_data)}")

    async def _log_response(
        self,
        response: Response,
        request_id: str,
        duration: float
    ):
        """Log response details."""
        log_data = {
            "request_id": request_id,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}s",
        }

        if self.log_headers:
            log_data["headers"] = self._sanitize_headers(dict(response.headers))

        if self.log_response_body and response.body:
            try:
                body = json.loads(response.body)
                log_data["body"] = self._sanitize_data(body)
            except:
                log_data["body"] = "Could not parse response body"

        logger.info(f"Outgoing response: {json.dumps(log_data)}")

    async def _log_error(
        self,
        error: Exception,
        request_id: str,
        duration: float
    ):
        """Log error details."""
        log_data = {
            "request_id": request_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "duration": f"{duration:.3f}s"
        }
        logger.error(f"Request error: {json.dumps(log_data)}")

    def _should_skip_logging(self, request: Request) -> bool:
        """Check if logging should be skipped for this request."""
        path = request.url.path
        return any(
            path.startswith(exclude_path)
            for exclude_path in self.exclude_paths
        )

    def _sanitize_headers(self, headers: dict) -> dict:
        """Remove sensitive information from headers."""
        return {
            k: v if k.lower() not in self.sensitive_headers else "[REDACTED]"
            for k, v in headers.items()
        }

    def _sanitize_data(self, data: dict) -> dict:
        """Remove sensitive information from data."""
        if not isinstance(data, dict):
            return data

        return {
            k: "[REDACTED]" if k in self.sensitive_fields
            else self._sanitize_data(v) if isinstance(v, dict)
            else v
            for k, v in data.items()
        }

    def _get_client_ip(self, request: Request) -> str:
        """Get the client's IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        import uuid
        return str(uuid.uuid4()) 