"""Redis event bus utility.

This module provides a Redis-based event bus implementation for pub/sub messaging.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable, Set

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisEventBus:
    """Asynchronous Redis-based event bus."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "events",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize event bus.
        
        Args:
            redis_client: Redis client instance
            prefix: Event key prefix
            max_retries: Maximum publish retries
            retry_delay: Delay between retries in seconds
        """
        self.redis = redis_client
        self.prefix = prefix
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._handlers: Dict[str, Set[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._running = False
        self._subscriber_task: Optional[asyncio.Task] = None
        self._pubsub: Optional[redis.client.PubSub] = None

    def _make_channel(self, event_type: str) -> str:
        """Create event channel name.
        
        Args:
            event_type: Event type identifier
            
        Returns:
            Channel name
        """
        return f"{self.prefix}:{event_type}"

    async def publish(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        retry_count: int = 0
    ) -> None:
        """Publish event.
        
        Args:
            event_type: Event type identifier
            event_data: Event data
            retry_count: Current retry attempt
            
        Raises:
            CacheOperationError: If publishing fails after retries
        """
        try:
            channel = self._make_channel(event_type)
            event = {
                "type": event_type,
                "data": event_data,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self.redis.publish(
                channel,
                json.dumps(event)
            )
            
        except RedisError as e:
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay)
                await self.publish(event_type, event_data, retry_count + 1)
            else:
                raise CacheOperationError(
                    message="Failed to publish event",
                    details={"event_type": event_type, "error": str(e)}
                )

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to events.
        
        Args:
            event_type: Event type identifier
            handler: Event handler function
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
            
            # Subscribe to channel if this is first handler
            if self._pubsub:
                channel = self._make_channel(event_type)
                await self._pubsub.subscribe(channel)
        
        self._handlers[event_type].add(handler)
        
        # Start subscriber if not running
        if not self._running:
            await self.start()

    async def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Unsubscribe from events.
        
        Args:
            event_type: Event type identifier
            handler: Event handler function
        """
        if event_type in self._handlers:
            self._handlers[event_type].discard(handler)
            
            # Unsubscribe from channel if no handlers left
            if not self._handlers[event_type] and self._pubsub:
                channel = self._make_channel(event_type)
                await self._pubsub.unsubscribe(channel)
                del self._handlers[event_type]

    async def start(self) -> None:
        """Start event subscriber."""
        if self._running:
            return
            
        self._running = True
        self._pubsub = self.redis.pubsub()
        
        # Subscribe to all channels
        for event_type in self._handlers:
            channel = self._make_channel(event_type)
            await self._pubsub.subscribe(channel)
            
        self._subscriber_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop event subscriber."""
        self._running = False
        
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None
            
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None

    async def _run(self) -> None:
        """Run subscriber loop."""
        if not self._pubsub:
            return
            
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message and message["type"] == "message":
                    # Parse event
                    event = json.loads(message["data"])
                    channel = message["channel"].decode()
                    event_type = channel.split(":", 1)[1]
                    
                    # Call handlers
                    if event_type in self._handlers:
                        await asyncio.gather(
                            *[
                                handler(event["data"])
                                for handler in self._handlers[event_type]
                            ],
                            return_exceptions=True
                        )
                        
            except asyncio.CancelledError:
                # Normal cancellation
                break
            except Exception as e:
                logger.error(
                    f"Error in subscriber loop: {str(e)}",
                    exc_info=True
                )
                await asyncio.sleep(1.0)

class EventBusManager:
    """Manager for creating event buses."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize event bus manager.
        
        Args:
            redis_client: Redis client instance
            max_retries: Default maximum publish retries
            retry_delay: Default delay between retries in seconds
        """
        self.redis = redis_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._event_buses: Dict[str, RedisEventBus] = {}

    def get_event_bus(
        self,
        prefix: str,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None
    ) -> RedisEventBus:
        """Get or create event bus.
        
        Args:
            prefix: Event bus prefix
            max_retries: Optional maximum publish retries
            retry_delay: Optional delay between retries in seconds
            
        Returns:
            RedisEventBus instance
        """
        if prefix not in self._event_buses:
            self._event_buses[prefix] = RedisEventBus(
                redis_client=self.redis,
                prefix=prefix,
                max_retries=max_retries or self.max_retries,
                retry_delay=retry_delay or self.retry_delay
            )
        return self._event_buses[prefix]

    async def start_event_buses(self) -> None:
        """Start all event buses."""
        for event_bus in self._event_buses.values():
            await event_bus.start()

    async def stop_event_buses(self) -> None:
        """Stop all event buses."""
        await asyncio.gather(
            *[event_bus.stop() for event_bus in self._event_buses.values()],
            return_exceptions=True
        ) 