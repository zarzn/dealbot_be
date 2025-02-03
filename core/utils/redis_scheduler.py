"""Redis scheduler utility.

This module provides a Redis-based scheduler implementation for recurring tasks.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisScheduler:
    """Asynchronous Redis-based task scheduler."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "scheduler",
        check_interval: float = 1.0
    ):
        """Initialize scheduler.
        
        Args:
            redis_client: Redis client instance
            prefix: Scheduler key prefix
            check_interval: Task check interval in seconds
        """
        self.redis = redis_client
        self.prefix = prefix
        self.check_interval = check_interval
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def _make_key(self, task_type: str) -> str:
        """Create scheduler key.
        
        Args:
            task_type: Task type identifier
            
        Returns:
            Scheduler key
        """
        return f"{self.prefix}:tasks:{task_type}"

    async def schedule(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        run_at: datetime,
        task_id: Optional[str] = None
    ) -> str:
        """Schedule a task.
        
        Args:
            task_type: Task type identifier
            task_data: Task data
            run_at: When to run the task
            task_id: Optional task ID
            
        Returns:
            Task ID
            
        Raises:
            CacheOperationError: If scheduling fails
        """
        try:
            key = self._make_key(task_type)
            task_id = task_id or f"{task_type}:{datetime.utcnow().timestamp()}"
            
            task = {
                "id": task_id,
                "type": task_type,
                "data": task_data,
                "run_at": run_at.timestamp(),
                "created_at": datetime.utcnow().timestamp()
            }
            
            # Add to sorted set with run_at as score
            await self.redis.zadd(
                key,
                {json.dumps(task): task["run_at"]}
            )
            
            return task_id
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to schedule task",
                details={"task_type": task_type, "error": str(e)}
            )

    async def schedule_recurring(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        interval: timedelta,
        task_id: Optional[str] = None,
        start_at: Optional[datetime] = None
    ) -> str:
        """Schedule a recurring task.
        
        Args:
            task_type: Task type identifier
            task_data: Task data
            interval: Time between runs
            task_id: Optional task ID
            start_at: Optional first run time
            
        Returns:
            Task ID
            
        Raises:
            CacheOperationError: If scheduling fails
        """
        try:
            key = self._make_key(task_type)
            task_id = task_id or f"{task_type}:recurring:{datetime.utcnow().timestamp()}"
            
            task = {
                "id": task_id,
                "type": task_type,
                "data": task_data,
                "interval": int(interval.total_seconds()),
                "run_at": (start_at or datetime.utcnow()).timestamp(),
                "created_at": datetime.utcnow().timestamp(),
                "recurring": True
            }
            
            # Add to sorted set with run_at as score
            await self.redis.zadd(
                key,
                {json.dumps(task): task["run_at"]}
            )
            
            return task_id
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to schedule recurring task",
                details={"task_type": task_type, "error": str(e)}
            )

    async def cancel(self, task_type: str, task_id: str) -> None:
        """Cancel a scheduled task.
        
        Args:
            task_type: Task type identifier
            task_id: Task ID
            
        Raises:
            CacheOperationError: If cancellation fails
        """
        try:
            key = self._make_key(task_type)
            
            # Find and remove task
            tasks = await self.redis.zrange(key, 0, -1, withscores=True)
            for task_data, _ in tasks:
                task = json.loads(task_data)
                if task["id"] == task_id:
                    await self.redis.zrem(key, task_data)
                    break
                    
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to cancel task",
                details={"task_type": task_type, "task_id": task_id, "error": str(e)}
            )

    async def register_handler(
        self,
        task_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register task handler.
        
        Args:
            task_type: Task type identifier
            handler: Task handler function
        """
        self._handlers[task_type] = handler
        
        # Start scheduler if not running
        if not self._running:
            await self.start()

    async def start(self) -> None:
        """Start task scheduler."""
        if self._running:
            return
            
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop task scheduler."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

    async def _run(self) -> None:
        """Run scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow().timestamp()
                
                # Check each task type
                for task_type in self._handlers:
                    key = self._make_key(task_type)
                    
                    # Get due tasks
                    tasks = await self.redis.zrangebyscore(
                        key,
                        0,
                        now,
                        withscores=True
                    )
                    
                    for task_data, score in tasks:
                        task = json.loads(task_data)
                        
                        try:
                            # Run task handler
                            await self._handlers[task_type](task["data"])
                            
                            # Remove task
                            await self.redis.zrem(key, task_data)
                            
                            # Reschedule if recurring
                            if task.get("recurring"):
                                next_run = score + task["interval"]
                                task["run_at"] = next_run
                                await self.redis.zadd(
                                    key,
                                    {json.dumps(task): next_run}
                                )
                                
                        except Exception as e:
                            logger.error(
                                f"Error running task {task['id']}: {str(e)}",
                                exc_info=True
                            )
                            
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                # Normal cancellation
                break
            except Exception as e:
                logger.error(
                    f"Error in scheduler loop: {str(e)}",
                    exc_info=True
                )
                await asyncio.sleep(self.check_interval)

class SchedulerManager:
    """Manager for creating schedulers."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        check_interval: float = 1.0
    ):
        """Initialize scheduler manager.
        
        Args:
            redis_client: Redis client instance
            check_interval: Default task check interval in seconds
        """
        self.redis = redis_client
        self.check_interval = check_interval
        self._schedulers: Dict[str, RedisScheduler] = {}

    def get_scheduler(
        self,
        prefix: str,
        check_interval: Optional[float] = None
    ) -> RedisScheduler:
        """Get or create scheduler.
        
        Args:
            prefix: Scheduler prefix
            check_interval: Optional task check interval in seconds
            
        Returns:
            RedisScheduler instance
        """
        if prefix not in self._schedulers:
            self._schedulers[prefix] = RedisScheduler(
                redis_client=self.redis,
                prefix=prefix,
                check_interval=check_interval or self.check_interval
            )
        return self._schedulers[prefix]

    async def start_schedulers(self) -> None:
        """Start all schedulers."""
        for scheduler in self._schedulers.values():
            await scheduler.start()

    async def stop_schedulers(self) -> None:
        """Stop all schedulers."""
        await asyncio.gather(
            *[scheduler.stop() for scheduler in self._schedulers.values()],
            return_exceptions=True
        ) 