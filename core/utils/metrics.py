from typing import Dict, Any, Optional
from datetime import datetime
import time
from prometheus_client import Counter, Histogram, Gauge, Summary
from functools import wraps
import asyncio

from .logger import get_logger

logger = get_logger(__name__)

# Request metrics
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"]
)

REQUEST_COUNT = Counter(
    "request_count_total",
    "Total request count",
    ["method", "endpoint", "status"]
)

# Custom metrics
CUSTOM_METRICS = Counter(
    "custom_metrics_total",
    "Custom metrics counter",
    ["metric_name", "category"]
)

# Database metrics
DB_QUERY_LATENCY = Histogram(
    "db_query_latency_seconds",
    "Database query latency in seconds",
    ["operation", "table"]
)

DB_CONNECTION_POOL = Gauge(
    "db_connection_pool_size",
    "Database connection pool size",
    ["pool_type"]
)

# Cache metrics
CACHE_HIT_COUNT = Counter(
    "cache_hit_total",
    "Cache hit count",
    ["cache_type"]
)

CACHE_MISS_COUNT = Counter(
    "cache_miss_total",
    "Cache miss count",
    ["cache_type"]
)

# External service metrics
EXTERNAL_REQUEST_LATENCY = Histogram(
    "external_request_latency_seconds",
    "External service request latency in seconds",
    ["service", "operation"]
)

EXTERNAL_REQUEST_COUNT = Counter(
    "external_request_count_total",
    "External service request count",
    ["service", "operation", "status"]
)

# Market metrics
MARKET_SEARCH_LATENCY = Histogram(
    "market_search_latency_seconds",
    "Market search latency in seconds",
    ["market_type"]
)

MARKET_SEARCH_COUNT = Counter(
    "market_search_count_total",
    "Market search count",
    ["market_type", "status"]
)

MARKET_PRODUCT_DETAILS_LATENCY = Histogram(
    "market_product_details_latency_seconds",
    "Market product details latency in seconds",
    ["market_type"]
)

MARKET_PRICE_HISTORY_LATENCY = Histogram(
    "market_price_history_latency_seconds",
    "Market price history latency in seconds",
    ["market_type"]
)

# Business metrics
DEAL_FOUND_COUNT = Counter(
    "deal_found_total",
    "Number of deals found",
    ["source", "category"]
)

GOAL_CREATED_COUNT = Counter(
    "goal_created_total",
    "Number of goals created",
    ["status"]
)

TOKEN_TRANSACTION_COUNT = Counter(
    "token_transaction_total",
    "Number of token transactions",
    ["type", "status"]
)

# System metrics
MEMORY_USAGE = Gauge(
    "memory_usage_bytes",
    "Memory usage in bytes",
    ["type"]
)

CPU_USAGE = Gauge(
    "cpu_usage_percent",
    "CPU usage percentage",
    ["type"]
)

def track_metric(metric_name: str, category: str = "default") -> None:
    """Track a custom metric.
    
    Args:
        metric_name: Name of the metric to track
        category: Category of the metric (default: "default")
    """
    try:
        CUSTOM_METRICS.labels(
            metric_name=metric_name,
            category=category
        ).inc()
    except Exception as e:
        logger.error(f"Error tracking custom metric {metric_name}: {str(e)}")

class MetricsCollector:
    """Metrics collection utility"""
    @staticmethod
    def track_search_cache_hit() -> None:
        """Track search cache hit."""
        try:
            CACHE_HIT_COUNT.labels(cache_type="search").inc()
        except Exception as e:
            logger.error(f"Error tracking search cache hit: {str(e)}")

    @staticmethod
    def track_product_details_cache_hit() -> None:
        """Track product details cache hit."""
        try:
            CACHE_HIT_COUNT.labels(cache_type="product_details").inc()
        except Exception as e:
            logger.error(f"Error tracking product details cache hit: {str(e)}")

    @staticmethod
    def track_market_search_error(market_type: str, error_type: str) -> None:
        """Track market search error."""
        try:
            MARKET_SEARCH_COUNT.labels(
                market_type=market_type,
                status="error"
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking market search error: {str(e)}")

    @staticmethod
    def track_request(method: str, endpoint: str, status: int, duration: float) -> None:
        """Track request metrics"""
        try:
            REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking request metrics: {str(e)}")

    @staticmethod
    def track_db_query(operation: str, table: str, duration: float) -> None:
        """Track database query metrics"""
        try:
            DB_QUERY_LATENCY.labels(
                operation=operation,
                table=table
            ).observe(duration)
        except Exception as e:
            logger.error(f"Error tracking DB query metrics: {str(e)}")

    @staticmethod
    def track_cache_operation(cache_type: str, hit: bool) -> None:
        """Track cache operation metrics"""
        try:
            if hit:
                CACHE_HIT_COUNT.labels(cache_type=cache_type).inc()
            else:
                CACHE_MISS_COUNT.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Error tracking cache metrics: {str(e)}")

    @staticmethod
    def track_external_request(
        service: str,
        operation: str,
        status: str,
        duration: float
    ) -> None:
        """Track external service request metrics"""
        try:
            EXTERNAL_REQUEST_LATENCY.labels(
                service=service,
                operation=operation
            ).observe(duration)
            
            EXTERNAL_REQUEST_COUNT.labels(
                service=service,
                operation=operation,
                status=status
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking external request metrics: {str(e)}")

    @staticmethod
    def track_market_search(
        query: str,
        results_count: int,
        search_time: float,
        successful_markets: int,
        failed_markets: int
    ) -> None:
        """Track market search metrics"""
        try:
            MARKET_SEARCH_LATENCY.labels(
                market_type="all"
            ).observe(search_time)
            
            MARKET_SEARCH_COUNT.labels(
                market_type="all",
                status="success" if failed_markets == 0 else "partial"
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking market search metrics: {str(e)}")

    @staticmethod
    def track_product_details(
        market_type: str,
        response_time: float
    ) -> None:
        """Track product details metrics"""
        try:
            MARKET_PRODUCT_DETAILS_LATENCY.labels(
                market_type=market_type
            ).observe(response_time)
        except Exception as e:
            logger.error(f"Error tracking product details metrics: {str(e)}")

    @staticmethod
    def track_price_history(
        market_type: str,
        history_points: int,
        response_time: float
    ) -> None:
        """Track price history metrics"""
        try:
            MARKET_PRICE_HISTORY_LATENCY.labels(
                market_type=market_type
            ).observe(response_time)
        except Exception as e:
            logger.error(f"Error tracking price history metrics: {str(e)}")

    @staticmethod
    def track_deal_found(source: str, category: str) -> None:
        """Track deal found metrics"""
        try:
            DEAL_FOUND_COUNT.labels(
                source=source,
                category=category
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking deal metrics: {str(e)}")

    @staticmethod
    def track_goal_created(status: str) -> None:
        """Track goal creation metrics"""
        try:
            GOAL_CREATED_COUNT.labels(status=status).inc()
        except Exception as e:
            logger.error(f"Error tracking goal metrics: {str(e)}")

    @staticmethod
    def track_token_transaction(transaction_type: str, status: str) -> None:
        """Track token transaction metrics"""
        try:
            TOKEN_TRANSACTION_COUNT.labels(
                type=transaction_type,
                status=status
            ).inc()
        except Exception as e:
            logger.error(f"Error tracking token transaction metrics: {str(e)}")

    @staticmethod
    def update_memory_usage(memory_type: str, usage: float) -> None:
        """Update memory usage metrics"""
        try:
            MEMORY_USAGE.labels(type=memory_type).set(usage)
        except Exception as e:
            logger.error(f"Error updating memory metrics: {str(e)}")

    @staticmethod
    def update_cpu_usage(cpu_type: str, usage: float) -> None:
        """Update CPU usage metrics"""
        try:
            CPU_USAGE.labels(type=cpu_type).set(usage)
        except Exception as e:
            logger.error(f"Error updating CPU metrics: {str(e)}")

def track_time(
    metric_type: str,
    labels: Optional[Dict[str, str]] = None
):
    """Decorator to track function execution time"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                if metric_type == "request":
                    MetricsCollector.track_request(
                        method=labels.get("method", ""),
                        endpoint=labels.get("endpoint", ""),
                        status=200,
                        duration=duration
                    )
                elif metric_type == "db_query":
                    MetricsCollector.track_db_query(
                        operation=labels.get("operation", ""),
                        table=labels.get("table", ""),
                        duration=duration
                    )
                elif metric_type == "external_request":
                    MetricsCollector.track_external_request(
                        service=labels.get("service", ""),
                        operation=labels.get("operation", ""),
                        status="success",
                        duration=duration
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                if metric_type == "request":
                    MetricsCollector.track_request(
                        method=labels.get("method", ""),
                        endpoint=labels.get("endpoint", ""),
                        status=500,
                        duration=duration
                    )
                elif metric_type == "external_request":
                    MetricsCollector.track_external_request(
                        service=labels.get("service", ""),
                        operation=labels.get("operation", ""),
                        status="error",
                        duration=duration
                    )
                
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if metric_type == "request":
                    MetricsCollector.track_request(
                        method=labels.get("method", ""),
                        endpoint=labels.get("endpoint", ""),
                        status=200,
                        duration=duration
                    )
                elif metric_type == "db_query":
                    MetricsCollector.track_db_query(
                        operation=labels.get("operation", ""),
                        table=labels.get("table", ""),
                        duration=duration
                    )
                elif metric_type == "external_request":
                    MetricsCollector.track_external_request(
                        service=labels.get("service", ""),
                        operation=labels.get("operation", ""),
                        status="success",
                        duration=duration
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                if metric_type == "request":
                    MetricsCollector.track_request(
                        method=labels.get("method", ""),
                        endpoint=labels.get("endpoint", ""),
                        status=500,
                        duration=duration
                    )
                elif metric_type == "external_request":
                    MetricsCollector.track_external_request(
                        service=labels.get("service", ""),
                        operation=labels.get("operation", ""),
                        status="error",
                        duration=duration
                    )
                
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator 

class MetricsManager:
    """Manages application metrics collection and reporting."""

    def __init__(self):
        self.request_latency = REQUEST_LATENCY
        self.request_count = REQUEST_COUNT
        self.db_query_latency = DB_QUERY_LATENCY
        self.db_connection_pool = DB_CONNECTION_POOL
        self.cache_hit_count = CACHE_HIT_COUNT
        self.cache_miss_count = CACHE_MISS_COUNT

    def record_request_latency(self, method: str, endpoint: str, duration: float) -> None:
        """Record request latency."""
        self.request_latency.labels(method=method, endpoint=endpoint).observe(duration)

    def record_request(self, method: str, endpoint: str, status: int) -> None:
        """Record request count."""
        self.request_count.labels(method=method, endpoint=endpoint, status=status).inc()

    def record_db_query(self, operation: str, table: str, duration: float) -> None:
        """Record database query latency."""
        self.db_query_latency.labels(operation=operation, table=table).observe(duration)

    def update_db_pool_size(self, pool_type: str, size: int) -> None:
        """Update database connection pool size."""
        self.db_connection_pool.labels(pool_type=pool_type).set(size)

    def record_cache_hit(self, cache_type: str) -> None:
        """Record cache hit."""
        self.cache_hit_count.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str) -> None:
        """Record cache miss."""
        self.cache_miss_count.labels(cache_type=cache_type).inc() 