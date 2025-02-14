"""Performance monitoring middleware."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from prometheus_client import Counter, Histogram

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

        # Initialize metrics
        self.request_latency = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"]
        )
        self.request_count = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"]
        )
        self.slow_requests = Counter(
            "http_slow_requests_total",
            "Total slow HTTP requests",
            ["method", "endpoint"]
        )

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

            # Record metrics
            self.request_latency.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            self.request_count.labels(
                method=method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()

            # Check for slow requests
            if duration > self.slow_request_threshold:
                self.slow_requests.labels(
                    method=method,
                    endpoint=endpoint
                ).inc()
                logger.warning(
                    f"Slow request detected: {method} {endpoint} "
                    f"took {duration:.2f} seconds"
                )

            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}"
            
            return response

        except Exception as e:
            duration = time.time() - start_time
            self.request_count.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()
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
                "total_requests": self.request_count._value.sum(),
                "slow_requests": self.slow_requests._value.sum(),
                "average_latency": self.request_latency._sum.sum() / max(self.request_latency._count.sum(), 1),
                "metrics": await self.metrics.get_all_metrics()
            }
        except Exception as e:
            logger.error(f"Failed to get performance stats: {str(e)}")
            return {} 