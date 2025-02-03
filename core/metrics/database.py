"""Database metrics collection module.

This module provides metrics collection for database operations using Prometheus client.
"""

from prometheus_client import Counter, Histogram
import time

class DatabaseMetrics:
    """Database metrics collector."""
    
    def __init__(self):
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