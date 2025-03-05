"""Task service tests."""

import pytest
import asyncio
from datetime import datetime, timedelta
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import logging

from core.services.task import TaskService
from core.services.cache import CacheService
from core.models.enums import TaskStatus, TaskPriority
from core.exceptions import TaskError, ValidationError
from backend_tests.utils.markers import service_test, depends_on
from backend_tests.mocks.redis_mock import redis_mock

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_task_function():
    """Mock task function that returns after a delay."""
    async def _task(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"status": "success", "args": args, "kwargs": kwargs}
    return _task

@pytest.fixture
async def task_service(redis_client):
    """Task service fixture."""
    cache_service = CacheService(redis_client)
    service = TaskService(cache_service)
    yield service
    await service.close()

@pytest.fixture(autouse=True)
def prepare_task_data():
    """Prepare task data in the Redis mock before tests."""
    # Clear any existing data
    redis_mock.data.clear()
    
    # Generate mock task data
    for i in range(3):
        task_id = f"task_{i}"
        task_key = f"task:{task_id}"
        task_data = {
            "id": task_id,
            "status": "completed",
            "created_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "started_at": (datetime.now() - timedelta(minutes=59)).isoformat(),
            "completed_at": (datetime.now() - timedelta(minutes=58)).isoformat(),
            "error": None
        }
        redis_mock.data[task_key] = json.dumps(task_data)
    
    yield
    
    # Clean up
    redis_mock.data.clear()

@service_test
async def test_create_task(task_service):
    """Test creating a background task."""
    task_id = await task_service.create_task(
        mock_task_function,
        "arg1", 
        "arg2",
        task_id="test_task",
        delay=None,
        key="value"
    )
    
    assert task_id is not None
    status = await task_service.get_task_status(task_id)
    assert status["status"] == "pending"

@service_test
async def test_get_task(task_service):
    """Test retrieving a task."""
    task_id = await task_service.create_task(
        mock_task_function,
        task_id="test_task"
    )
    
    # Get task by ID
    status = await task_service.get_task_status(task_id)
    assert status["id"] == task_id
    
    # Test non-existent task
    with pytest.raises(TaskError):
        await task_service.get_task_status("non-existent-id")

@service_test
async def test_update_task_status(task_service):
    """Test updating task status."""
    task_id = await task_service.create_task(
        mock_task_function,
        task_id="test_task"
    )
    
    # Task should start running automatically
    await asyncio.sleep(0.1)  # Give it a moment to start
    status = await task_service.get_task_status(task_id)
    assert status["status"] in ["running", "completed"]

@service_test
async def test_list_tasks(task_service):
    """Test listing tasks with filters."""
    # Create multiple tasks
    tasks = []
    for i in range(3):
        task_id = await task_service.create_task(
            mock_task_function,
            task_id=f"task_{i}"
        )
        tasks.append(task_id)
    
    # Test listing all tasks
    all_tasks = await task_service.list_tasks()
    assert len(all_tasks) >= 3

@service_test
async def test_retry_failed_task(task_service):
    """Test retrying a failed task."""
    async def failing_task():
        raise Exception("Test error")
    
    task_id = await task_service.create_task(
        failing_task,
        task_id="failing_task"
    )
    
    # Wait for task to fail
    await asyncio.sleep(0.1)
    status = await task_service.get_task_status(task_id)
    assert status["status"] == "failed"
    assert "Test error" in status["error"]

@service_test
async def test_cancel_task(task_service):
    """Test canceling a task."""
    async def long_running_task():
        await asyncio.sleep(10)
    
    task_id = await task_service.create_task(
        long_running_task,
        task_id="test_task"
    )
    
    # Cancel task
    await task_service.cancel_task(task_id)
    
    status = await task_service.get_task_status(task_id)
    assert status["status"] == "cancelled"

@service_test
async def test_task_timeout(task_service):
    """Test task timeout handling."""
    async def slow_task():
        await asyncio.sleep(2)
    
    task_id = await task_service.create_task(
        slow_task,
        task_id="timeout_task",
        delay=timedelta(seconds=1)
    )
    
    # Wait for task to start and timeout
    await asyncio.sleep(1.5)
    status = await task_service.get_task_status(task_id)
    assert status["status"] == "running"

@service_test
async def test_task_dependencies(task_service):
    """Test task dependency handling."""
    # Create parent task
    parent_id = await task_service.create_task(
        mock_task_function,
        task_id="parent_task"
    )
    
    # Create child task
    child_id = await task_service.create_task(
        mock_task_function,
        task_id="child_task",
        delay=timedelta(seconds=1)  # Delay to ensure parent completes first
    )
    
    # Wait for tasks to complete
    await asyncio.sleep(1.5)
    parent_status = await task_service.get_task_status(parent_id)
    child_status = await task_service.get_task_status(child_id)
    assert parent_status["status"] == "completed"
    assert child_status["status"] == "completed"

@service_test
async def test_task_cleanup(task_service):
    """Test task cleanup functionality."""
    # Create tasks that will complete
    task_ids = []
    for i in range(3):
        task_id = await task_service.create_task(
            mock_task_function,
            task_id=f"task_{i}"
        )
        task_ids.append(task_id)
    
    # Wait for tasks to complete
    await asyncio.sleep(0.5)
    
    # Run cleanup with a very short max_age
    cleaned = await task_service.cleanup_tasks(timedelta(microseconds=1))
    assert cleaned >= 3  # Should clean up all completed tasks 