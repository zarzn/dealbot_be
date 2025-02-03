"""Redis metrics collector utility.

This module provides a Redis-based metrics collector implementation.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisMetrics:
    """Asynchronous Redis-based metrics collector."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str,
        retention_days: int = 30
    ):
        """Initialize metrics collector.
        
        Args:
            redis_client: Redis client instance
            prefix: Metrics key prefix
            retention_days: Data retention period in days
        """
        self.redis = redis_client
        self.prefix = prefix
        self.retention_days = retention_days

    def _make_key(self, metric: str, timestamp: Optional[datetime] = None) -> str:
        """Create metrics key.
        
        Args:
            metric: Metric name
            timestamp: Optional timestamp for time-based keys
            
        Returns:
            Metrics key
        """
        if timestamp:
            date_str = timestamp.strftime("%Y%m%d")
            return f"{self.prefix}:metrics:{metric}:{date_str}"
        return f"{self.prefix}:metrics:{metric}"

    async def increment(
        self,
        metric: str,
        amount: int = 1,
        timestamp: Optional[datetime] = None
    ) -> int:
        """Increment counter metric.
        
        Args:
            metric: Metric name
            amount: Amount to increment by
            timestamp: Optional timestamp for time-based metrics
            
        Returns:
            New counter value
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            value = await self.redis.incrby(key, amount)
            
            if timestamp:
                # Set expiry for time-based metrics
                expiry = timestamp + timedelta(days=self.retention_days)
                await self.redis.expireat(key, int(expiry.timestamp()))
                
            return value
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to increment metric",
                details={"metric": metric, "error": str(e)}
            )

    async def gauge(
        self,
        metric: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Set gauge metric.
        
        Args:
            metric: Metric name
            value: Gauge value
            timestamp: Optional timestamp for time-based metrics
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            await self.redis.set(key, value)
            
            if timestamp:
                expiry = timestamp + timedelta(days=self.retention_days)
                await self.redis.expireat(key, int(expiry.timestamp()))
                
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to set gauge metric",
                details={"metric": metric, "error": str(e)}
            )

    async def histogram(
        self,
        metric: str,
        value: float,
        timestamp: Optional[datetime] = None,
        buckets: Optional[List[float]] = None
    ) -> None:
        """Record histogram metric.
        
        Args:
            metric: Metric name
            value: Value to record
            timestamp: Optional timestamp for time-based metrics
            buckets: Optional histogram buckets
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            
            if not buckets:
                buckets = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10]
                
            async with self.redis.pipeline() as pipe:
                # Record raw value
                await pipe.rpush(f"{key}:values", value)
                
                # Update bucket counters
                for bucket in buckets:
                    if value <= bucket:
                        await pipe.hincrby(f"{key}:buckets", str(bucket), 1)
                        
                if timestamp:
                    expiry = timestamp + timedelta(days=self.retention_days)
                    await pipe.expireat(f"{key}:values", int(expiry.timestamp()))
                    await pipe.expireat(f"{key}:buckets", int(expiry.timestamp()))
                    
                await pipe.execute()
                
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to record histogram metric",
                details={"metric": metric, "error": str(e)}
            )

    async def timer(
        self,
        metric: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record timer metric.
        
        Args:
            metric: Metric name
            value: Time value in seconds
            timestamp: Optional timestamp for time-based metrics
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            
            async with self.redis.pipeline() as pipe:
                # Record raw value
                await pipe.rpush(f"{key}:values", value)
                
                # Update summary statistics
                await pipe.hincrby(f"{key}:stats", "count", 1)
                await pipe.hincrbyfloat(f"{key}:stats", "sum", value)
                
                if value < float(await self.redis.hget(f"{key}:stats", "min") or "inf"):
                    await pipe.hset(f"{key}:stats", "min", value)
                if value > float(await self.redis.hget(f"{key}:stats", "max") or "0"):
                    await pipe.hset(f"{key}:stats", "max", value)
                    
                if timestamp:
                    expiry = timestamp + timedelta(days=self.retention_days)
                    await pipe.expireat(f"{key}:values", int(expiry.timestamp()))
                    await pipe.expireat(f"{key}:stats", int(expiry.timestamp()))
                    
                await pipe.execute()
                
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to record timer metric",
                details={"metric": metric, "error": str(e)}
            )

    async def get_counter(
        self,
        metric: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Union[int, Dict[str, int]]:
        """Get counter metric value(s).
        
        Args:
            metric: Metric name
            start_time: Optional start time for time range
            end_time: Optional end time for time range
            
        Returns:
            Counter value or dict of date -> value
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            if not start_time and not end_time:
                # Get simple counter value
                key = self._make_key(metric)
                value = await self.redis.get(key)
                return int(value or 0)
                
            # Get time range values
            values = {}
            current = start_time
            while current <= end_time:
                key = self._make_key(metric, current)
                value = await self.redis.get(key)
                values[current.date().isoformat()] = int(value or 0)
                current += timedelta(days=1)
                
            return values
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get counter metric",
                details={"metric": metric, "error": str(e)}
            )

    async def get_gauge(
        self,
        metric: str,
        timestamp: Optional[datetime] = None
    ) -> float:
        """Get gauge metric value.
        
        Args:
            metric: Metric name
            timestamp: Optional timestamp for time-based metrics
            
        Returns:
            Gauge value
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            value = await self.redis.get(key)
            return float(value or 0)
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get gauge metric",
                details={"metric": metric, "error": str(e)}
            )

    async def get_histogram(
        self,
        metric: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get histogram metric data.
        
        Args:
            metric: Metric name
            timestamp: Optional timestamp for time-based metrics
            
        Returns:
            Dictionary containing histogram data
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            
            # Get raw values
            values = [float(v) for v in await self.redis.lrange(f"{key}:values", 0, -1)]
            
            # Get bucket counts
            buckets = {
                float(k): int(v)
                for k, v in (await self.redis.hgetall(f"{key}:buckets")).items()
            }
            
            return {
                "values": values,
                "buckets": buckets,
                "count": len(values),
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "avg": sum(values) / len(values) if values else 0
            }
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get histogram metric",
                details={"metric": metric, "error": str(e)}
            )

    async def get_timer(
        self,
        metric: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get timer metric data.
        
        Args:
            metric: Metric name
            timestamp: Optional timestamp for time-based metrics
            
        Returns:
            Dictionary containing timer data
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            key = self._make_key(metric, timestamp)
            
            # Get raw values
            values = [float(v) for v in await self.redis.lrange(f"{key}:values", 0, -1)]
            
            # Get summary statistics
            stats = await self.redis.hgetall(f"{key}:stats")
            
            return {
                "values": values,
                "count": int(stats.get("count", 0)),
                "sum": float(stats.get("sum", 0)),
                "min": float(stats.get("min", 0)),
                "max": float(stats.get("max", 0)),
                "avg": float(stats.get("sum", 0)) / int(stats.get("count", 1))
            }
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get timer metric",
                details={"metric": metric, "error": str(e)}
            )

class MetricsManager:
    """Manager for creating metrics collectors."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        retention_days: int = 30
    ):
        """Initialize metrics manager.
        
        Args:
            redis_client: Redis client instance
            retention_days: Default data retention period in days
        """
        self.redis = redis_client
        self.retention_days = retention_days
        self._collectors: Dict[str, RedisMetrics] = {}

    def get_collector(
        self,
        prefix: str,
        retention_days: Optional[int] = None
    ) -> RedisMetrics:
        """Get or create metrics collector.
        
        Args:
            prefix: Metrics key prefix
            retention_days: Optional data retention period in days
            
        Returns:
            RedisMetrics instance
        """
        if prefix not in self._collectors:
            self._collectors[prefix] = RedisMetrics(
                redis_client=self.redis,
                prefix=prefix,
                retention_days=retention_days or self.retention_days
            )
        return self._collectors[prefix] 