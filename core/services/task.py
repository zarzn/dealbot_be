"""Task service for managing background tasks and job queues."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID, uuid4

from core.exceptions import TaskError
from core.services.cache import CacheService

logger = logging.getLogger(__name__)

class TaskService:
    """Service for managing background tasks and job queues."""

    def __init__(self, cache_service: CacheService):
        """Initialize task service with cache service."""
        self._cache = cache_service
        self._prefix = "task:"
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = True

    async def create_task(
        self,
        func: Callable,
        *args: Any,
        task_id: Optional[str] = None,
        delay: Optional[Union[int, timedelta]] = None,
        **kwargs: Any
    ) -> str:
        """Create a new background task."""
        try:
            task_id = task_id or str(uuid4())
            task_key = f"{self._prefix}{task_id}"

            # Store task metadata
            metadata = {
                "id": task_id,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "started_at": None,
                "completed_at": None,
                "error": None
            }
            
            # Make sure metadata is stored before task starts
            await self._cache.set(task_key, metadata)
            
            # Log task creation for debugging
            logger.info(f"Creating task: {task_id}")

            # Create and schedule task
            async def wrapped_task():
                try:
                    if delay:
                        if isinstance(delay, timedelta):
                            delay_seconds = delay.total_seconds()
                        else:
                            delay_seconds = delay
                        await asyncio.sleep(delay_seconds)

                    # Update status to running
                    metadata = await self._cache.get(task_key)
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {
                            "id": task_id,
                            "status": "pending",
                            "created_at": datetime.utcnow().isoformat()
                        }
                    
                    metadata["status"] = "running"
                    metadata["started_at"] = datetime.utcnow().isoformat()
                    await self._cache.set(task_key, metadata)

                    # Execute the task function
                    result = await func(*args, **kwargs)

                    # Update status to completed
                    metadata = await self._cache.get(task_key)
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {
                            "id": task_id,
                            "status": "running",
                            "created_at": datetime.utcnow().isoformat(),
                            "started_at": datetime.utcnow().isoformat()
                        }
                        
                    metadata["status"] = "completed"
                    metadata["completed_at"] = datetime.utcnow().isoformat()
                    await self._cache.set(task_key, metadata)

                    return result
                except Exception as e:
                    # Update status to failed
                    metadata = await self._cache.get(task_key)
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {
                            "id": task_id,
                            "status": "running",
                            "created_at": datetime.utcnow().isoformat(),
                            "started_at": datetime.utcnow().isoformat()
                        }
                        
                    metadata["status"] = "failed"
                    metadata["error"] = str(e)
                    await self._cache.set(task_key, metadata)
                    logger.error(f"Task {task_id} failed: {str(e)}")
                    raise
                finally:
                    # Remove from active tasks
                    if task_id in self._tasks:
                        del self._tasks[task_id]

            # Start the task
            task = asyncio.create_task(wrapped_task())
            self._tasks[task_id] = task
            
            return task_id

        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            raise TaskError(f"Task creation failed: {str(e)}")

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a task."""
        try:
            task_key = f"{self._prefix}{task_id}"
            metadata = await self._cache.get(task_key)
            if metadata is None:
                raise TaskError(f"Task {task_id} not found")
                
            # If the metadata is a string (serialized JSON), deserialize it
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in task metadata for task {task_id}")
                    
            return metadata
        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}")
            raise TaskError(f"Task status check failed: {str(e)}")

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        try:
            task = self._tasks.get(task_id)
            if task is None:
                raise TaskError(f"Task {task_id} not found")

            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            task_key = f"{self._prefix}{task_id}"
            metadata = await self._cache.get(task_key)
            if metadata:
                metadata["status"] = "cancelled"
                await self._cache.set(task_key, metadata)

            return True
        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}")
            raise TaskError(f"Task cancellation failed: {str(e)}")

    async def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        try:
            tasks = []
            cursor = 0
            pattern = f"{self._prefix}*"
            
            while True:
                # Use scan to find all task keys
                cursor, keys = await self._cache.scan(cursor, match=pattern)
                
                for key in keys:
                    # Extract the key without the prefix for retrieval
                    task_key = key
                    if isinstance(key, bytes):
                        task_key = key.decode('utf-8')
                    
                    # Make sure task_key has the prefix for fetching
                    if not task_key.startswith(self._prefix):
                        task_key = f"{self._prefix}{task_key}"
                        
                    # Get task metadata
                    metadata = await self._cache.get(task_key)
                    
                    # Handle JSON string data
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in task metadata for task {task_key}")
                            continue
                    
                    if metadata and (status is None or metadata.get("status") == status):
                        # Ensure task_id is properly extracted
                        task_id = key
                        if isinstance(task_id, bytes):
                            task_id = task_id.decode('utf-8')
                        if task_id.startswith(self._prefix):
                            task_id = task_id[len(self._prefix):]
                        
                        # Add task_id to metadata if not present
                        if "id" not in metadata:
                            metadata["id"] = task_id
                            
                        tasks.append(metadata)
                
                # Break if we've completed the scan
                if cursor == 0:
                    break
                
            return tasks
        except Exception as e:
            logger.error(f"Error listing tasks: {str(e)}")
            raise TaskError(f"Task listing failed: {str(e)}")

    async def cleanup_tasks(self, max_age: timedelta) -> int:
        """Clean up old completed/failed/cancelled tasks."""
        try:
            count = 0
            cutoff = datetime.utcnow() - max_age
            cursor = 0
            pattern = f"{self._prefix}*"
            
            while True:
                # Use scan to find all task keys
                cursor, keys = await self._cache.scan(cursor, match=pattern)
                
                for key in keys:
                    # Extract the key without the prefix for retrieval
                    task_key = key
                    if isinstance(key, bytes):
                        task_key = key.decode('utf-8')
                    
                    # Make sure task_key has the prefix for fetching
                    if not task_key.startswith(self._prefix):
                        task_key = f"{self._prefix}{task_key}"
                        
                    # Get task metadata
                    metadata = await self._cache.get(task_key)
                    
                    # Handle JSON string data
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in task metadata for task {task_key}")
                            continue
                            
                    if metadata and metadata.get("status") in ["completed", "failed", "cancelled"]:
                        # Check if the task has a completed_at timestamp
                        completed_at = None
                        if "completed_at" in metadata:
                            try:
                                completed_at = datetime.fromisoformat(metadata["completed_at"])
                            except ValueError:
                                # Skip if the timestamp is invalid
                                logger.warning(f"Invalid timestamp for task {task_key}")
                                continue
                        elif "started_at" in metadata:
                            # Fallback to started_at if completed_at is not available
                            try:
                                completed_at = datetime.fromisoformat(metadata["started_at"])
                            except ValueError:
                                continue
                        else:
                            # Fallback to created_at
                            try:
                                completed_at = datetime.fromisoformat(metadata["created_at"])
                            except ValueError:
                                continue
                                
                        if completed_at and completed_at < cutoff:
                            # Make sure we're deleting with the full key
                            if not task_key.startswith(self._prefix):
                                task_key = f"{self._prefix}{task_key}"
                            await self._cache.delete(task_key)
                            count += 1
                
                # Break if we've completed the scan
                if cursor == 0:
                    break
                
            return count
        except Exception as e:
            logger.error(f"Error cleaning up tasks: {str(e)}")
            raise TaskError(f"Task cleanup failed: {str(e)}")

    async def close(self) -> None:
        """Close task service and cancel all running tasks."""
        try:
            self._running = False
            for task_id, task in list(self._tasks.items()):
                if not task.done():
                    await self.cancel_task(task_id)
            self._tasks.clear()
        except Exception as e:
            logger.error(f"Error closing task service: {str(e)}")
            raise TaskError(f"Task service close failed: {str(e)}")

    def is_running(self) -> bool:
        """Check if task service is running."""
        return self._running 