"""Performance monitoring middleware."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings
from core.utils.logger import get_logger
from core.utils.metrics import MetricsManager

logger = get_logger(__name__)

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring request performance."""

    def __init__(
        self,
        app: ASGIApp,
        metrics_manager: MetricsManager = None,
        slow_request_threshold: float = settings.SLOW_REQUEST_THRESHOLD
    ):
        super().__init__(app)
        self.metrics = metrics_manager or MetricsManager()
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request with performance monitoring."""
        start_time = time.time()
        method = request.method
        endpoint = request.url.path

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Record metrics using MetricsManager
            self.metrics.record_request_latency(
                method=method,
                endpoint=endpoint,
                duration=duration
            )

            self.metrics.record_request(
                method=method,
                endpoint=endpoint,
                status=response.status_code
            )

            # Check for slow requests
            if duration > self.slow_request_threshold:
                logger.warning(
                    f"Slow request detected: {method} {endpoint} "
                    f"took {duration:.2f} seconds"
                )

            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}"
            
            return response

        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_request(
                method=method,
                endpoint=endpoint,
                status=500
            )
            logger.error(
                f"Request failed: {method} {endpoint} "
                f"after {duration:.2f} seconds: {str(e)}"
            )
            raise

    async def record_custom_metric(
        self,
        name: str,
        value: float,
        labels: dict = None
    ):
        """Record a custom metric."""
        try:
            await self.metrics.record_metric(name, value, labels)
        except Exception as e:
            logger.error(f"Failed to record metric {name}: {str(e)}")

    async def get_performance_stats(self) -> dict:
        """Get current performance statistics."""
        try:
            return {
                "total_requests": self.metrics.request_count._value.sum(),
                "average_latency": self.metrics.request_latency._sum.sum() / max(self.metrics.request_latency._count.sum(), 1),
                "metrics": await self.metrics.get_all_metrics()
            }
        except Exception as e:
            logger.error(f"Failed to get performance stats: {str(e)}")
            return {} 