"""Redis queue utility.

This module provides a Redis-based queue implementation for background tasks.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Awaitable, TypeVar, Generic

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RedisQueue(Generic[T]):
    """Asynchronous Redis-based queue."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        queue_name: str,
        visibility_timeout: int = 30,
        retention_days: int = 7
    ):
        """Initialize queue.
        
        Args:
            redis_client: Redis client instance
            queue_name: Queue name
            visibility_timeout: Message visibility timeout in seconds
            retention_days: Message retention period in days
        """
        self.redis = redis_client
        self.queue_name = queue_name
        self.visibility_timeout = visibility_timeout
        self.retention_days = retention_days
        
        # Queue keys
        self.queue_key = f"queue:{queue_name}"
        self.processing_key = f"queue:{queue_name}:processing"
        self.dead_letter_key = f"queue:{queue_name}:dead_letter"

    async def enqueue(
        self,
        message: T,
        delay: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add message to queue.
        
        Args:
            message: Message to enqueue
            delay: Optional delay in seconds
            metadata: Optional message metadata
            
        Returns:
            Message ID
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            data = {
                "id": message_id,
                "message": message,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
                "available_at": (now + timedelta(seconds=delay or 0)).isoformat(),
                "attempts": 0
            }
            
            serialized = json.dumps(data)
            
            if delay:
                # Add to delayed set
                await self.redis.zadd(
                    f"{self.queue_key}:delayed",
                    {serialized: now.timestamp() + delay}
                )
            else:
                # Add to main queue
                await self.redis.rpush(self.queue_key, serialized)
            
            return message_id
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to enqueue message",
                details={"queue": self.queue_name, "error": str(e)}
            )

    async def dequeue(self, count: int = 1) -> List[Dict[str, Any]]:
        """Get messages from queue.
        
        Args:
            count: Maximum number of messages to get
            
        Returns:
            List of message dictionaries
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            # Move delayed messages that are ready
            await self._move_delayed_messages()
            
            messages = []
            for _ in range(count):
                # Move message from queue to processing set
                data = await self.redis.lpop(self.queue_key)
                if not data:
                    break
                    
                message = json.loads(data)
                message["attempts"] += 1
                message["processing_started"] = datetime.utcnow().isoformat()
                
                # Add to processing set with expiry
                serialized = json.dumps(message)
                await self.redis.setex(
                    f"{self.processing_key}:{message['id']}",
                    self.visibility_timeout,
                    serialized
                )
                
                messages.append(message)
                
            return messages
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to dequeue messages",
                details={"queue": self.queue_name, "error": str(e)}
            )

    async def complete(self, message_id: str) -> None:
        """Mark message as completed.
        
        Args:
            message_id: Message ID
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            # Remove from processing set
            await self.redis.delete(f"{self.processing_key}:{message_id}")
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to complete message",
                details={"queue": self.queue_name, "message_id": message_id, "error": str(e)}
            )

    async def fail(
        self,
        message_id: str,
        error: Optional[str] = None,
        retry: bool = True
    ) -> None:
        """Mark message as failed.
        
        Args:
            message_id: Message ID
            error: Optional error message
            retry: Whether to retry the message
            
        Raises:
            CacheOperationError: If operation fails
        """
        try:
            # Get message from processing set
            key = f"{self.processing_key}:{message_id}"
            data = await self.redis.get(key)
            if not data:
                return
                
            message = json.loads(data)
            message["failed_at"] = datetime.utcnow().isoformat()
            message["error"] = error
            
            if retry and message["attempts"] < 3:
                # Return to queue for retry
                message["available_at"] = (
                    datetime.utcnow() + timedelta(seconds=2 ** message["attempts"])
                ).isoformat()
                await self.redis.rpush(self.queue_key, json.dumps(message))
            else:
                # Move to dead letter queue
                await self.redis.rpush(self.dead_letter_key, json.dumps(message))
                
            # Remove from processing set
            await self.redis.delete(key)
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to fail message",
                details={"queue": self.queue_name, "message_id": message_id, "error": str(e)}
            )

    async def _move_delayed_messages(self) -> None:
        """Move delayed messages that are ready to main queue."""
        try:
            now = datetime.utcnow().timestamp()
            
            # Get ready messages
            messages = await self.redis.zrangebyscore(
                f"{self.queue_key}:delayed",
                0,
                now
            )
            
            if not messages:
                return
                
            # Move to main queue
            async with self.redis.pipeline() as pipe:
                for message in messages:
                    await pipe.rpush(self.queue_key, message)
                    await pipe.zrem(f"{self.queue_key}:delayed", message)
                await pipe.execute()
                
        except RedisError as e:
            logger.error(f"Failed to move delayed messages: {str(e)}")

    async def requeue_timed_out(self) -> None:
        """Requeue timed out messages."""
        try:
            # Scan processing set for timed out messages
            pattern = f"{self.processing_key}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    # Get message data
                    data = await self.redis.mget(keys)
                    
                    for message_data in data:
                        if not message_data:
                            continue
                            
                        message = json.loads(message_data)
                        started = datetime.fromisoformat(message["processing_started"])
                        
                        if datetime.utcnow() - started > timedelta(seconds=self.visibility_timeout):
                            # Message has timed out, requeue it
                            await self.fail(message["id"], "Processing timeout", retry=True)
                            
                if cursor == 0:
                    break
                    
        except RedisError as e:
            logger.error(f"Failed to requeue timed out messages: {str(e)}")

class QueueWorker(Generic[T]):
    """Worker for processing queue messages."""
    
    def __init__(
        self,
        queue: RedisQueue[T],
        handler: Callable[[T, Dict[str, Any]], Awaitable[None]],
        batch_size: int = 10,
        poll_interval: float = 1.0
    ):
        """Initialize worker.
        
        Args:
            queue: Queue to process
            handler: Message handler function
            batch_size: Number of messages to process in batch
            poll_interval: Queue polling interval in seconds
        """
        self.queue = queue
        self.handler = handler
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Start processing messages."""
        self._running = True
        
        while self._running:
            try:
                # Get messages from queue
                messages = await self.queue.dequeue(self.batch_size)
                
                if not messages:
                    await asyncio.sleep(self.poll_interval)
                    continue
                    
                # Process messages
                for message in messages:
                    task = asyncio.create_task(self._process_message(message))
                    self._tasks.append(task)
                    
                # Clean up completed tasks
                self._tasks = [t for t in self._tasks if not t.done()]
                
            except Exception as e:
                logger.error(f"Error processing messages: {str(e)}")
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop processing messages."""
        self._running = False
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process a single message.
        
        Args:
            message: Message data
        """
        try:
            # Call message handler
            await self.handler(message["message"], message["metadata"])
            
            # Mark message as completed
            await self.queue.complete(message["id"])
            
        except Exception as e:
            logger.error(f"Error processing message {message['id']}: {str(e)}")
            
            # Mark message as failed
            await self.queue.fail(
                message["id"],
                str(e),
                retry=True
            )

class QueueManager:
    """Manager for creating queues and workers."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        visibility_timeout: int = 30,
        retention_days: int = 7
    ):
        """Initialize queue manager.
        
        Args:
            redis_client: Redis client instance
            visibility_timeout: Default message visibility timeout in seconds
            retention_days: Default message retention period in days
        """
        self.redis = redis_client
        self.visibility_timeout = visibility_timeout
        self.retention_days = retention_days
        self._queues: Dict[str, RedisQueue] = {}
        self._workers: Dict[str, QueueWorker] = {}

    def create_queue(
        self,
        name: str,
        visibility_timeout: Optional[int] = None,
        retention_days: Optional[int] = None
    ) -> RedisQueue:
        """Create a new queue.
        
        Args:
            name: Queue name
            visibility_timeout: Optional message visibility timeout in seconds
            retention_days: Optional message retention period in days
            
        Returns:
            RedisQueue instance
        """
        if name not in self._queues:
            self._queues[name] = RedisQueue(
                redis_client=self.redis,
                queue_name=name,
                visibility_timeout=visibility_timeout or self.visibility_timeout,
                retention_days=retention_days or self.retention_days
            )
        return self._queues[name]

    def create_worker(
        self,
        queue_name: str,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[None]],
        batch_size: int = 10,
        poll_interval: float = 1.0
    ) -> QueueWorker:
        """Create a new worker.
        
        Args:
            queue_name: Queue name
            handler: Message handler function
            batch_size: Number of messages to process in batch
            poll_interval: Queue polling interval in seconds
            
        Returns:
            QueueWorker instance
        """
        queue = self.create_queue(queue_name)
        
        if queue_name not in self._workers:
            self._workers[queue_name] = QueueWorker(
                queue=queue,
                handler=handler,
                batch_size=batch_size,
                poll_interval=poll_interval
            )
        return self._workers[queue_name]

    async def start_workers(self) -> None:
        """Start all workers."""
        for worker in self._workers.values():
            asyncio.create_task(worker.start())

    async def stop_workers(self) -> None:
        """Stop all workers."""
        await asyncio.gather(
            *[worker.stop() for worker in self._workers.values()],
            return_exceptions=True
        ) 