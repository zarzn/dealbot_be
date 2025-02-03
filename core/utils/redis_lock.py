"""Redis lock utility.

This module provides a Redis-based distributed locking implementation.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisLock:
    """Asynchronous Redis-based distributed lock."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "lock",
        default_timeout: int = 30,  # 30 seconds
        extend_threshold: float = 0.5  # Extend at 50% of timeout
    ):
        """Initialize lock.
        
        Args:
            redis_client: Redis client instance
            prefix: Lock key prefix
            default_timeout: Default lock timeout in seconds
            extend_threshold: When to extend lock (fraction of timeout)
        """
        self.redis = redis_client
        self.prefix = prefix
        self.default_timeout = default_timeout
        self.extend_threshold = extend_threshold
        self._locks: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, lock_name: str) -> str:
        """Create lock key.
        
        Args:
            lock_name: Lock identifier
            
        Returns:
            Lock key
        """
        return f"{self.prefix}:{lock_name}"

    async def acquire(
        self,
        lock_name: str,
        timeout: Optional[int] = None,
        wait: bool = True,
        wait_timeout: Optional[float] = None,
        lock_id: Optional[str] = None
    ) -> Optional[str]:
        """Acquire lock.
        
        Args:
            lock_name: Lock identifier
            timeout: Lock timeout in seconds
            wait: Whether to wait for lock
            wait_timeout: How long to wait for lock
            lock_id: Optional lock ID
            
        Returns:
            Lock ID if acquired, None if not
            
        Raises:
            CacheOperationError: If lock operation fails
        """
        try:
            key = self._make_key(lock_name)
            lock_id = lock_id or str(uuid.uuid4())
            timeout = timeout or self.default_timeout
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # Try to acquire lock
                acquired = await self.redis.set(
                    key,
                    lock_id,
                    ex=timeout,
                    nx=True
                )
                
                if acquired:
                    # Store lock info
                    self._locks[lock_name] = {
                        "id": lock_id,
                        "key": key,
                        "timeout": timeout,
                        "acquired_at": start_time,
                        "extend_task": None
                    }
                    
                    # Start extend task if threshold > 0
                    if self.extend_threshold > 0:
                        extend_interval = timeout * self.extend_threshold
                        extend_task = asyncio.create_task(
                            self._extend_lock(lock_name, extend_interval)
                        )
                        self._locks[lock_name]["extend_task"] = extend_task
                        
                    return lock_id
                    
                if not wait:
                    return None
                    
                # Check wait timeout
                if wait_timeout is not None:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= wait_timeout:
                        return None
                        
                # Wait before retry
                await asyncio.sleep(0.1)
                
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to acquire lock",
                details={"lock_name": lock_name, "error": str(e)}
            )

    async def release(
        self,
        lock_name: str,
        lock_id: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """Release lock.
        
        Args:
            lock_name: Lock identifier
            lock_id: Optional lock ID to verify ownership
            force: Whether to force release without ID check
            
        Returns:
            Whether lock was released
            
        Raises:
            CacheOperationError: If lock release fails
        """
        try:
            key = self._make_key(lock_name)
            
            # Stop extend task if running
            if lock_name in self._locks:
                extend_task = self._locks[lock_name]["extend_task"]
                if extend_task:
                    extend_task.cancel()
                    try:
                        await extend_task
                    except asyncio.CancelledError:
                        pass
                del self._locks[lock_name]
            
            # Check lock ID if provided
            if lock_id and not force:
                current_id = await self.redis.get(key)
                if not current_id or current_id.decode() != lock_id:
                    return False
                    
            # Release lock
            await self.redis.delete(key)
            return True
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to release lock",
                details={"lock_name": lock_name, "error": str(e)}
            )

    async def extend(
        self,
        lock_name: str,
        timeout: Optional[int] = None,
        lock_id: Optional[str] = None
    ) -> bool:
        """Extend lock timeout.
        
        Args:
            lock_name: Lock identifier
            timeout: New timeout in seconds
            lock_id: Optional lock ID to verify ownership
            
        Returns:
            Whether lock was extended
            
        Raises:
            CacheOperationError: If lock extension fails
        """
        try:
            key = self._make_key(lock_name)
            timeout = timeout or self.default_timeout
            
            # Check lock ID if provided
            if lock_id:
                current_id = await self.redis.get(key)
                if not current_id or current_id.decode() != lock_id:
                    return False
                    
            # Extend lock
            extended = await self.redis.expire(key, timeout)
            return bool(extended)
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to extend lock",
                details={"lock_name": lock_name, "error": str(e)}
            )

    async def _extend_lock(
        self,
        lock_name: str,
        interval: float
    ) -> None:
        """Periodically extend lock.
        
        Args:
            lock_name: Lock identifier
            interval: Extension interval in seconds
        """
        try:
            while True:
                await asyncio.sleep(interval)
                
                if lock_name not in self._locks:
                    break
                    
                lock_info = self._locks[lock_name]
                await self.extend(
                    lock_name,
                    timeout=lock_info["timeout"],
                    lock_id=lock_info["id"]
                )
                
        except asyncio.CancelledError:
            # Normal cancellation
            pass
        except Exception as e:
            logger.error(
                f"Error extending lock {lock_name}: {str(e)}",
                exc_info=True
            )

class LockManager:
    """Manager for creating locks."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        default_timeout: int = 30,
        extend_threshold: float = 0.5
    ):
        """Initialize lock manager.
        
        Args:
            redis_client: Redis client instance
            default_timeout: Default lock timeout in seconds
            extend_threshold: Default extend threshold
        """
        self.redis = redis_client
        self.default_timeout = default_timeout
        self.extend_threshold = extend_threshold
        self._locks: Dict[str, RedisLock] = {}

    def get_lock(
        self,
        prefix: str,
        default_timeout: Optional[int] = None,
        extend_threshold: Optional[float] = None
    ) -> RedisLock:
        """Get or create lock.
        
        Args:
            prefix: Lock prefix
            default_timeout: Optional default timeout in seconds
            extend_threshold: Optional extend threshold
            
        Returns:
            RedisLock instance
        """
        if prefix not in self._locks:
            self._locks[prefix] = RedisLock(
                redis_client=self.redis,
                prefix=prefix,
                default_timeout=default_timeout or self.default_timeout,
                extend_threshold=extend_threshold or self.extend_threshold
            )
        return self._locks[prefix] 