# Test Utilities

This directory contains utilities to help with testing the AI Agentic Deals System.

## Test Timeout Helper

The `test_timeout_helper.py` module provides utilities to prevent tests from hanging due to unhandled asyncio tasks, unclosed connections, or other common issues.

### Common Issues Addressed

1. **Unresolved Promises**: Async functions that never complete
2. **Unclosed Connections**: Database, Redis, or other connections that aren't properly closed
3. **Pending Tasks**: Background tasks that are created but never awaited or cancelled
4. **Infinite Loops**: Code that gets stuck in infinite loops
5. **Missing Exception Handling**: Tests that wait indefinitely for a response that won't come

### How to Use

#### Automatic Solution (Recommended)

The timeout helper is automatically applied to all async tests via the `conftest.py` file. This provides:

1. Automatic timeout for all async tests
2. Cleanup of pending tasks after each test
3. Cleanup of unclosed connections after each test
4. Monitoring of task creation

#### Manual Usage in Tests

For additional control, you can use the provided decorators and fixtures:

```python
import pytest
from backend_tests.utils.test_timeout_helper import with_timeout

@pytest.mark.asyncio
@with_timeout(10)  # Custom timeout of 10 seconds for this test
async def test_something_slow():
    # Your test code here
    pass
```

#### Fixtures

Add these fixtures to your tests:

```python
@pytest.mark.asyncio
async def test_with_cleanup(prevent_test_hanging):
    # Test will clean up resources automatically
    pass
```

#### Tracking Connections

Register connections for automatic cleanup:

```python
from backend_tests.utils.test_timeout_helper import register_connection

# In your test
async def test_with_connection():
    conn = await create_connection()
    register_connection(conn)  # Will be closed automatically at test end
```

#### Safe Task Creation

Create tasks that will be monitored and cleaned up:

```python
from backend_tests.utils.test_timeout_helper import create_monitored_task

async def test_with_background_task():
    # This task will be tracked and cancelled if not completed
    task = create_monitored_task(some_coroutine())
    await task
```

### Best Practices for Avoiding Hanging Tests

1. **Always await async functions**: Never leave coroutines unawaited
2. **Close connections explicitly**: Always close database, Redis, and other connections
3. **Cancel background tasks**: Always cancel tasks you create
4. **Use timeouts with asyncio.wait**: `await asyncio.wait([task], timeout=5.0)`
5. **Avoid infinite loops**: Add a counter or timeout to all loops
6. **Handle exceptions properly**: Don't swallow exceptions that might hide issues

By following these practices and using the timeout helper, you can avoid tests that hang indefinitely. 