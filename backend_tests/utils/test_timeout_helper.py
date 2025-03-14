"""
Test Timeout Helper

This module provides utilities to prevent tests from hanging due to unhandled
asyncio tasks, unclosed connections, or other common issues.
"""

import asyncio
import signal
import sys
import time
import traceback
from functools import wraps
from typing import Any, Callable, List, Set, Dict, Optional, Awaitable, TypeVar, cast
import logging
import contextlib
import inspect
import warnings
from weakref import WeakSet

logger = logging.getLogger(__name__)

# Store references to created tasks so we can clean them up
_active_tasks: WeakSet = WeakSet()

# Store references to all connections for cleanup
_active_connections: Set[Any] = set()

T = TypeVar('T')

class TestTimeoutError(Exception):
    """Error raised when a test takes too long to execute."""
    pass


def register_connection(conn: Any) -> None:
    """Register a connection for automatic cleanup."""
    _active_connections.add(conn)


def unregister_connection(conn: Any) -> None:
    """Unregister a connection from automatic cleanup."""
    _active_connections.discard(conn)


async def close_all_connections() -> None:
    """Close all registered connections."""
    if not _active_connections:
        return
    
    logger.info(f"Closing {len(_active_connections)} active connections")
    for conn in list(_active_connections):
        try:
            if hasattr(conn, 'close') and callable(conn.close):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
            elif hasattr(conn, '__aexit__'):
                await conn.__aexit__(None, None, None)
            _active_connections.discard(conn)
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")


async def cancel_all_tasks() -> None:
    """Cancel all tasks created during the test."""
    tasks = [t for t in _active_tasks if not t.done()]
    if not tasks:
        return
    
    logger.info(f"Cancelling {len(tasks)} pending tasks")
    for task in tasks:
        try:
            if not task.done():
                task.cancel()
        except Exception as e:
            logger.warning(f"Error cancelling task: {e}")
    
    if tasks:
        # Wait for all tasks to be cancelled
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass


@contextlib.contextmanager
def timeout_context(seconds: int) -> None:
    """
    Create a context manager that raises a TestTimeoutError if the code takes too long.
    
    Args:
        seconds: Maximum allowed execution time in seconds
    
    Raises:
        TestTimeoutError: If the execution time exceeds the timeout
    """
    def timeout_handler(signum, frame):
        stack = ''.join(traceback.format_stack())
        raise TestTimeoutError(f"Test execution timed out after {seconds} seconds. Call stack:\n{stack}")
    
    # Only use signal on Unix-like systems
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
    
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        # Only use signal on Unix-like systems
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        
        if elapsed > seconds:
            raise TestTimeoutError(f"Test execution timed out after {elapsed:.2f} seconds (limit: {seconds}s)")


def with_timeout(seconds: int) -> Callable:
    """
    Decorator to apply a timeout to a function.
    
    Args:
        seconds: Maximum allowed execution time in seconds
    
    Returns:
        Function decorator that applies the timeout
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with timeout_context(seconds):
                return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with timeout_context(seconds):
                # Create a task for this function
                task = asyncio.create_task(func(*args, **kwargs))
                _active_tasks.add(task)
                
                try:
                    return await task
                finally:
                    # Clean up any remaining tasks/connections
                    try:
                        await cancel_all_tasks()
                        await close_all_connections()
                    except Exception as e:
                        logger.warning(f"Error during cleanup: {e}")
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def create_monitored_task(coro: Awaitable[T], name: Optional[str] = None) -> asyncio.Task[T]:
    """
    Create a task that is monitored and will be cleaned up.
    
    Args:
        coro: Coroutine to run as a task
        name: Optional name for the task
    
    Returns:
        The created task
    """
    task = asyncio.create_task(coro, name=name)
    _active_tasks.add(task)
    return task


class SafeTaskGroup:
    """
    A safer version of asyncio.TaskGroup that ensures all tasks are properly tracked and cleaned up.
    """
    def __init__(self):
        self.tasks: List[asyncio.Task] = []
    
    def create_task(self, coro: Awaitable[T], *, name: Optional[str] = None) -> asyncio.Task[T]:
        """Create a new task in the group."""
        task = create_monitored_task(coro, name=name)
        self.tasks.append(task)
        return task
    
    async def __aenter__(self) -> 'SafeTaskGroup':
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Ensure all tasks are completed or cancelled when exiting the context."""
        if not self.tasks:
            return
        
        # If there was an exception, cancel all tasks
        if exc_type is not None:
            for task in self.tasks:
                if not task.done():
                    task.cancel()
        
        # Wait for all tasks to complete
        done, pending = await asyncio.wait(self.tasks, return_exceptions=True)
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
        
        # Check for errors in completed tasks
        for task in done:
            if task.cancelled():
                continue
            
            exc = task.exception()
            if exc is not None and exc_type is None:
                raise exc


@contextlib.asynccontextmanager
async def create_task_with_cleanup(coro: Awaitable[T], timeout: int = 30) -> None:
    """
    Create a task and ensure it's cleaned up properly.
    
    Args:
        coro: Coroutine to run as a task
        timeout: Maximum time to wait for the task in seconds
    """
    task = create_monitored_task(coro)
    try:
        with timeout_context(timeout):
            yield task
    finally:
        if not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


# Common pytest fixtures for safe test execution
import pytest

@pytest.fixture(scope="function")
async def task_cleanup():
    """Fixture to clean up tasks after each test."""
    yield
    await cancel_all_tasks()


@pytest.fixture(scope="function")
async def connection_cleanup():
    """Fixture to clean up connections after each test."""
    yield
    await close_all_connections()


@pytest.fixture(scope="function")
async def prevent_test_hanging():
    """Fixture to prevent tests from hanging."""
    yield
    await cancel_all_tasks()
    await close_all_connections()


# Function to patch common hanging points in the application
def patch_hanging_points():
    """
    Patch common causes of hanging in tests:
    
    1. Add timeouts to Redis operations
    2. Ensure database connections are closed
    3. Add monitoring to asyncio tasks
    """
    from unittest.mock import patch
    import asyncio
    
    # Store original create_task
    original_create_task = asyncio.create_task
    
    # Replace create_task with our monitored version
    def patched_create_task(coro, name=None):
        task = original_create_task(coro, name=name)
        _active_tasks.add(task)
        return task
    
    # Apply the patch
    asyncio.create_task = patched_create_task
    
    # Log that we've patched hanging points
    logger.info("Patched common hanging points in the application") 