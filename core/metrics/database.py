"""Database metrics collection module.

This module provides metrics collection for database operations using Prometheus client.
"""

from prometheus_client import Counter, Histogram, Gauge
import time
from typing import Optional

class DatabaseMetrics:
    """Database metrics collector."""
    
    _instance: Optional['DatabaseMetrics'] = None
    
    def __new__(cls) -> 'DatabaseMetrics':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized') or not self._initialized:
            self.connection_checkouts = Counter(
                'db_connection_checkouts_total',
                'Total number of database connection checkouts'
            )
            self.connection_checkins = Counter(
                'db_connection_checkins_total',
                'Total number of database connection checkins'
            )
            self.connection_failures = Counter(
                'db_connection_failures_total',
                'Total number of database connection failures'
            )
            self.successful_transactions = Counter(
                'db_successful_transactions_total',
                'Total number of successful database transactions'
            )
            self.failed_transactions = Counter(
                'db_failed_transactions_total',
                'Total number of failed database transactions'
            )
            self.transaction_duration = Histogram(
                'db_transaction_duration_seconds',
                'Database transaction duration in seconds',
                buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
            )
            self.slow_queries = Counter(
                'db_slow_queries_total',
                'Total number of slow database queries'
            )
            self.query_execution_time = Histogram(
                'db_query_execution_time_seconds',
                'Database query execution time in seconds',
                buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
            )
            
            # Connection pool metrics
            self.pool_connections_used = Gauge(
                'db_pool_connections_used',
                'Number of connections currently in use from the pool'
            )
            self.pool_connections_overflow = Gauge(
                'db_pool_connections_overflow',
                'Number of overflow connections currently in use'
            )
            self.pool_utilization_percent = Gauge(
                'db_pool_utilization_percent',
                'Percentage of pool connections currently in use'
            )
            self.pool_size = Gauge(
                'db_pool_size',
                'Total size of the connection pool'
            )
            
            # Connection cleanup metrics
            self.idle_connections_cleaned = Counter(
                'db_idle_connections_cleaned_total',
                'Total number of idle database connections cleaned up'
            )
            
            self._initialized = True

    def connection_checkout(self):
        """Record a connection checkout."""
        self.connection_checkouts.inc()

    def connection_checkin(self):
        """Record a connection checkin."""
        self.connection_checkins.inc()

    def connection_failure(self):
        """Record a connection failure."""
        self.connection_failures.inc()

    def successful_transaction(self):
        """Record a successful transaction."""
        self.successful_transactions.inc()

    def failed_transaction(self):
        """Record a failed transaction."""
        self.failed_transactions.inc()

    def transaction_time(self, duration: float):
        """Record transaction duration."""
        self.transaction_duration.observe(duration)
        
    def record_slow_query(self):
        """Record a slow query."""
        self.slow_queries.inc()
        
    def record_query_time(self, duration: float):
        """Record query execution time."""
        self.query_execution_time.observe(duration)
    
    def update_pool_usage_metrics(self, used: int, overflow: int, total_size: int):
        """Update connection pool usage metrics.
        
        Args:
            used: Number of connections currently in use
            overflow: Number of overflow connections in use
            total_size: Total size of the connection pool
        """
        self.pool_connections_used.set(used)
        self.pool_connections_overflow.set(overflow)
        self.pool_size.set(total_size)
        
        # Calculate utilization percentage
        if total_size > 0:
            utilization = (used / total_size) * 100
            self.pool_utilization_percent.set(utilization)
        
    @property
    def connection_failures_count(self) -> int:
        """Get the current count of connection failures."""
        return self.connection_failures._value.get()
        
    @property
    def slow_queries_count(self) -> int:
        """Get the current count of slow queries."""
        return self.slow_queries._value.get() 