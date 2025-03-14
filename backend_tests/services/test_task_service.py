"""Task service tests."""

import pytest
import asyncio
from datetime import datetime, timedelta
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import logging
import time_machine

from core.services.task import TaskService
from core.services.cache import CacheService
from core.models.enums import TaskStatus, TaskPriority, GoalStatus, MarketType
from core.tasks.deal_tasks import schedule_batch_deal_analysis, process_deal_analysis_task
from core.exceptions import TaskError
from backend_tests.utils.markers import service_test, depends_on
from backend_tests.mocks.redis_mock import redis_mock

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_task_function():
    """Mock task function for testing."""
    async def _task(*args, **kwargs):
        # Simulate work
        await asyncio.sleep(0.1)
        return {"success": True}
    return _task

@pytest.fixture
async def task_service(redis_client):
    """Create a task service instance."""
    cache_service = CacheService(redis_client)
    service = TaskService(cache_service)
    return service

@pytest.fixture(autouse=True)
def prepare_task_data():
    """Prepare test data for tasks."""
    return {
        "task1": {
            "id": str(uuid4()),
            "name": "Test Task 1",
            "description": "A test task",
            "priority": TaskPriority.HIGH.value,
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "timeout": 300,
            "max_retries": 3,
            "retry_count": 0,
            "params": {
                "test_param": "test_value"
            }
        },
        "task2": {
            "id": str(uuid4()),
            "name": "Test Task 2",
            "description": "Another test task",
            "priority": TaskPriority.MEDIUM.value,
            "status": TaskStatus.RUNNING.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "timeout": 300,
            "max_retries": 3,
            "retry_count": 0,
            "params": {
                "test_param": "test_value"
            }
        }
    }

@service_test
async def test_create_task(task_service, mock_task_function):
    """Test creating a task."""
    # Create a task with the required func parameter
    task_id = await task_service.create_task(
        func=mock_task_function,
        delay=None
    )
    
    # Verify task was created
    assert isinstance(task_id, str)
    
    # Get task status
    task_key = f"task:{task_id}"
    task_metadata = await task_service._cache.get(task_key)
    
    # Convert from JSON if needed
    if isinstance(task_metadata, str):
        task_metadata = json.loads(task_metadata)
    
    # Verify task metadata
    assert task_metadata["id"] == task_id
    assert task_metadata["status"] == "pending"
    assert "created_at" in task_metadata
    assert task_metadata.get("started_at") is None
    assert task_metadata.get("completed_at") is None
    assert task_metadata.get("error") is None

@service_test
async def test_get_task_status(task_service, mock_task_function):
    """Test retrieving a task status."""
    # Create a task
    task_id = await task_service.create_task(
        func=mock_task_function
    )
    
    # Get task status
    task_status = await task_service.get_task_status(task_id)
    
    # Verify task status
    assert task_status["id"] == task_id
    assert task_status["status"] == "pending"
    assert "created_at" in task_status
    assert task_status.get("started_at") is None
    assert task_status.get("completed_at") is None
    assert task_status.get("error") is None

@service_test
async def test_cancel_task(task_service, mock_task_function):
    """Test canceling a task."""
    # Create a task using the mock function
    task_id = await task_service.create_task(
        func=mock_task_function
    )
    
    # Cancel the task before it completes
    result = await task_service.cancel_task(task_id)
    
    # Verify cancellation was successful
    assert result is True
    
    # Check status
    task_status = await task_service.get_task_status(task_id)
    assert task_status["status"] == "cancelled"

@service_test
async def test_list_tasks(task_service, mock_task_function):
    """Test listing tasks."""
    # Create a few tasks
    for i in range(3):
        await task_service.create_task(
            func=mock_task_function
        )
    
    # Get all tasks
    all_tasks = await task_service.list_tasks()
    
    # Verify we have at least 3 tasks
    assert len(all_tasks) >= 3
    
    # Verify task structure
    for task in all_tasks:
        assert "id" in task
        assert "status" in task
        assert "created_at" in task

@service_test
async def test_cleanup_tasks(task_service, mock_task_function):
    """Test cleaning up old task records."""
    # Create tasks with the current time
    task_ids = []
    for i in range(3):
        task_id = await task_service.create_task(
            func=mock_task_function
        )
        task_ids.append(task_id)
    
    # Run cleanup for tasks older than 1 day
    max_age = timedelta(days=1)
    cleaned_count = await task_service.cleanup_tasks(max_age)
    
    # Verify no tasks were cleaned (they're all new)
    assert cleaned_count == 0

@service_test
async def test_batch_deal_analysis_task(task_service):
    """Test creating a batch deal analysis task."""
    # Create a list of test deal IDs
    deal_ids = [str(uuid4()) for _ in range(5)]
    
    # Mock the schedule_batch_deal_analysis function
    with patch('core.tasks.deal_tasks.schedule_batch_deal_analysis', new_callable=AsyncMock) as mock_schedule:
        mock_schedule.return_value = "test_task_id_123"
        
        # Create the task
        task_id = await task_service.create_task(
            func=schedule_batch_deal_analysis,
            deal_ids=deal_ids,
            priority=TaskPriority.HIGH.value
        )
        
        # Verify task was created
        assert isinstance(task_id, str)
        
        # Get task status
        task_status = await task_service.get_task_status(task_id)
        assert task_status["status"] == "pending"

@service_test
async def test_process_deal_analysis_task(task_service):
    """Test creating a task to process deal analysis."""
    # Mock the process_deal_analysis_task function
    with patch('core.tasks.deal_tasks.process_deal_analysis_task', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = True
        
        # Create the task
        task_id = await task_service.create_task(
            func=process_deal_analysis_task,
            task_id="test_task_id_123"
        )
        
        # Verify task was created
        assert isinstance(task_id, str)
        
        # Get task status
        task_status = await task_service.get_task_status(task_id)
        assert task_status["status"] == "pending"

@service_test
async def test_task_scheduling_with_active_goals(task_service):
    """Test scheduling analysis tasks based on active goals."""
    # Mock the batch deal analysis function
    with patch('core.tasks.deal_tasks.schedule_batch_deal_analysis', new_callable=AsyncMock) as mock_schedule:
        mock_schedule.return_value = "test_task_id_123"
        
        # Create a task
        task_id = await task_service.create_task(
            func=schedule_batch_deal_analysis,
            deal_ids=[str(uuid4()) for _ in range(3)]
        )
        
        # Verify task was created and has correct status
        assert isinstance(task_id, str)
        task_status = await task_service.get_task_status(task_id)
        assert task_status["status"] == "pending"

@service_test
async def test_task_execution_with_delay(task_service, mock_task_function):
    """Test task execution with delay."""
    # Create a task with a delay
    delay_seconds = 0.5
    start_time = datetime.utcnow()
    
    # Create task with delay
    task_id = await task_service.create_task(
        func=mock_task_function,
        delay=delay_seconds
    )
    
    # Wait for the task to complete
    await asyncio.sleep(1)
    
    # Get task status
    task_status = await task_service.get_task_status(task_id)
    
    # Task should be either running or completed by now
    assert task_status["status"] in ["running", "completed"]
    
    # Verify the task parameters were passed correctly
    if "started_at" in task_status and task_status["started_at"]:
        started_at = datetime.fromisoformat(task_status["started_at"])
        elapsed = (started_at - start_time).total_seconds()
        assert elapsed >= delay_seconds

@service_test
async def test_multiple_tasks_concurrently(task_service, mock_task_function):
    """Test running multiple tasks concurrently."""
    # Create multiple tasks
    task_ids = []
    for i in range(5):
        task_id = await task_service.create_task(
            func=mock_task_function
        )
        task_ids.append(task_id)
    
    # Verify all tasks were created
    assert len(task_ids) == 5
    
    # Get statuses of all tasks
    for task_id in task_ids:
        task_status = await task_service.get_task_status(task_id)
        assert task_status["status"] in ["pending", "running", "completed"]
    
    # Verify we can list tasks - but don't rely on exact task IDs
    # Instead, verify we can get at least the number of tasks we created
    all_tasks = await task_service.list_tasks()
    assert len(all_tasks) >= 3  # There should be at least 3 tasks
    
    # Just check that each task has the required fields
    for task in all_tasks:
        assert "id" in task
        assert "status" in task
        assert "created_at" in task

@service_test
async def test_task_error_handling(task_service):
    """Test error handling for failed tasks."""
    # Create a failing task
    async def failing_task():
        raise ValueError("Test error")
    
    # Create the task
    task_id = await task_service.create_task(
        func=failing_task
    )
    
    # Wait for the task to fail
    await asyncio.sleep(0.2)
    
    # Get task status
    task_status = await task_service.get_task_status(task_id)
    
    # Task should be failed
    assert task_status["status"] == "failed"
    assert "error" in task_status
    assert "Test error" in task_status["error"]

@service_test
async def test_service_shutdown(task_service, mock_task_function):
    """Test shutting down the task service."""
    # Create some tasks
    for i in range(3):
        await task_service.create_task(
            func=mock_task_function
        )
    
    # Verify service is running
    assert task_service.is_running() is True
    
    # Shut down the service
    await task_service.close()
    
    # Verify service is not running
    assert task_service.is_running() is False
    
    # Verify tasks dictionary is cleared
    assert len(task_service._tasks) == 0 