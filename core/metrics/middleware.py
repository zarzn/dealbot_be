"""Middleware metrics for monitoring system performance."""

from prometheus_client import Counter, Histogram

class MiddlewareMetrics:
    """Collection of metrics for middleware monitoring."""

    def __init__(self):
        """Initialize middleware metrics."""
        self.requests_total = Counter(
            'http_requests_total',
            'Total count of HTTP requests',
            ['method', 'path', 'status']
        )
        
        self.request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'path', 'status']
        )
        
        self.rate_limits_total = Counter(
            'rate_limits_total',
            'Total count of rate limit checks',
            ['client_id', 'window', 'result']
        )
        
        self.auth_total = Counter(
            'auth_attempts_total',
            'Total count of authentication attempts',
            ['user_id', 'result']
        )

    def request_started(self, method: str, path: str) -> None:
        """Record request start."""
        self.requests_total.labels(method=method, path=path, status="started").inc()

    def request_completed(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """Record completed request."""
        self.requests_total.labels(
            method=method,
            path=path,
            status=status_code
        ).inc()
        
        self.request_duration_seconds.labels(
            method=method,
            path=path,
            status=status_code
        ).observe(duration_ms / 1000.0)

    def request_failed(
        self,
        method: str,
        path: str,
        error_type: str,
        duration_ms: float
    ) -> None:
        """Record failed request."""
        self.requests_total.labels(
            method=method,
            path=path,
            status="error"
        ).inc()
        
        self.request_duration_seconds.labels(
            method=method,
            path=path,
            status="error"
        ).observe(duration_ms / 1000.0)

    def rate_limit_exceeded(self, client_id: str, window: str) -> None:
        """Record rate limit exceeded."""
        self.rate_limits_total.labels(
            client_id=client_id,
            window=window,
            result="exceeded"
        ).inc()

    def rate_limit_allowed(self, client_id: str) -> None:
        """Record rate limit allowed."""
        self.rate_limits_total.labels(
            client_id=client_id,
            window="all",
            result="allowed"
        ).inc()

    def auth_success(self, user_id: str) -> None:
        """Record successful authentication."""
        self.auth_total.labels(
            user_id=user_id,
            result="success"
        ).inc()

    def auth_failed(self, reason: str) -> None:
        """Record failed authentication."""
        self.auth_total.labels(
            user_id="unknown",
            result=f"failed_{reason}"
        ).inc() 