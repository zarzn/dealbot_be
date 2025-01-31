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

class MetricsCollector:
    """Metrics collection utility"""
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