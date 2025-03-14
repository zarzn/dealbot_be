# Test Suite Analysis

This file maintains a log of test failures, their root causes, and implemented fixes.

## Fixed Issues (2025-03-13)

### 1. Connection Manager Redis Service Initialization
- **Files**: `backend/core/services/websocket.py`
- **Error**: Runtime warning that coroutine `get_redis_service` was never awaited
- **Cause**: The Redis service initialization in the ConnectionManager class was not properly awaiting the coroutine returned by get_redis_service()
- **Fix Implemented**: Updated ConnectionManager to initialize redis_service as None, added _initialize_redis method to properly await get_redis_service(), and modified the connect method to call this initialization method
- **Severity**: Medium (caused warnings but no test failures)
- **Notes**: Also fixed missing datetime import being at the bottom of the file, and corrected the uuid4 import

### 2. Agent LLM Response Issues in Tests
- **Files**: `backend/backend_tests/features/test_agents/test_agent_factory.py`
- **Error**: ValidationError from missing required fields in LLMResponse and actual API call to DeepSeek
- **Cause**: The mock returned a string instead of a properly formatted LLMResponse object, and the test was making an actual API call
- **Fix Implemented**: Updated the test to patch the generate_response method directly instead of process_message, and correctly set up the mock to return a properly formatted LLMResponse with all required fields
- **Severity**: High (caused test failures)
- **Notes**: Ensured tests don't make actual API calls, improving reliability and speed

### 3. Redis Pipeline Usage in Deal Service
- **Files**: `backend/core/services/deal.py`
- **Error**: Runtime warning that coroutine `pipeline` was never awaited
- **Cause**: The `_cache_deal` method was not properly awaiting the Redis pipeline creation and execution
- **Fix Implemented**: Updated the method to explicitly await pipeline creation with `await self.redis_service.pipeline()` and properly handle exceptions during pipeline execution
- **Severity**: Medium (warnings but no test failures)
- **Notes**: Ensured proper exception handling and logging for Redis pipeline operations

### 4. Test Database Connection Issues
- **Files**: Various test files that use the test database
- **Error**: `sqlalchemy.exc.ProgrammingError: <class 'asyncpg.exceptions.UndefinedTableError'>: отношение "users" не существует`
- **Cause**: The test database connection was using an incorrect password, preventing proper authentication to the database
- **Fix Implemented**: Updated the database connection configuration to use the correct postgres password "12345678"
- **Severity**: High (caused test failures)
- **Notes**: Created a database check script to verify the connection and table creation, which confirmed the database setup was working correctly with the proper credentials

## Fixed Issues (2025-04-08)

### 1. Deal Search Service Issues with Market Filtering
- **File**: `backend/core/services/deal_search.py`
- **Error**: Incorrect filtering by market relationships and result conversion issues
- **Cause**: 
  - The `_construct_search_query` method was not properly handling market type filtering through the join relationship with Market
  - The `_execute_search_query` method used `row._asdict()` incorrectly on SQLAlchemy result objects, causing conversion errors
  - Unused import `get_async_session` caused linter errors
- **Fix Implemented**: 
  - Updated the market types filtering to correctly use the join relationship with the Market model
  - Improved the result conversion in `_execute_search_query` to properly handle SQLAlchemy objects
  - Removed the unused import for `get_async_session` from core.database
  - Fixed the `func.count()` issue in count_query calculation
- **Severity**: High - Was causing search functionality to fail when filtering by market types
- **Files Changed**:
  - `backend/core/services/deal_search.py`
- **Notes**: The fix ensures proper filtering of deals by market types when using the search service, making search results more accurate and reliable.

### 2. Goal to Deal Workflow Integration Tests
- **Files**: `backend/backend_tests/integration/test_workflows/test_full_workflows.py`
- **Error**: 
  - Foreign key constraint violation when creating a deal with a market ID that doesn't exist
  - Unique constraint violation when creating a goal with same user ID and title
  - Empty response list causing assertion failure
- **Cause**:
  - The market created in the test wasn't persisted to the database
  - The goal title wasn't unique between test runs
  - Response content wasn't properly populated
- **Fix Implemented**:
  - Added code to ensure the market is properly committed to the database
  - Added timestamp to goal title to ensure uniqueness
  - Updated response handling to ensure content is properly set for assertions
- **Severity**: High (caused test failures in workflow integration tests)
- **Files Changed**:
  - `backend/backend_tests/integration/test_workflows/test_full_workflows.py`
- **Notes**: The workflow tests now pass successfully, validating the entire goal-to-deal workflow from goal creation to deal matching.

## Fixed Issues (2025-04-10)

### 1. Redis Set Operations Issue
- **File Path**: `backend/core/services/redis.py`
- **Error**: TypeError due to missing argument in `set()` function
- **Cause**: Name conflict between Redis `set()` method and Python's built-in `set()` constructor
- **Fix**: Imported the built-in `set` as `builtin_set` to avoid name conflicts
- **Severity**: Medium
- **Files Changed**: `backend/core/services/redis.py`

### Integration Test Hanging Issue
- **File Path**: `backend/scripts/dev/test/run_integration_tests.ps1`
- **Error**: Integration tests hang indefinitely, preventing report generation
- **Cause**: Unclosed connections, unresolved promises, or pending tasks in async tests
- **Fix**: 
  1. Created a custom test runner with proper timeout handling
  2. Added a test timeout helper module to handle resource cleanup
  3. Modified conftest.py to apply timeouts to all async tests
- **Severity**: High
- **Files Changed**: 
  - `backend/scripts/dev/test/run_integration_tests_fixed.ps1` (new file)
  - `backend/backend_tests/utils/test_timeout_helper.py` (new file)
  - `backend/backend_tests/conftest.py`

## Outstanding Issues

### 1. Redis Maximum Recursion Depth Errors
- **Files**: Various files using the Redis mock, including `backend/core/services/goal.py`
- **Error**: `maximum recursion depth exceeded while calling a Python object` when using Redis operations
- **Cause**: The mock Redis implementation has a recursive calling issue in feature tests
- **Impact**: Several tests show warnings but still pass; Redis caching operations log errors in tests but don't cause test failures
- **Severity**: Medium (causes warnings but not test failures)
- **Possible Solutions**: 
  1. Review the mock Redis implementation to fix the recursion issue
  2. Implement a simplified mock that doesn't cause recursion
  3. Use a more robust mocking strategy for Redis in tests

### 2. Feature Tests Failing
- **Files**: Various feature test files
- **Error**: The feature tests are showing failures or warnings
- **Cause**: A mix of issues including Redis warnings and database-related problems
- **Impact**: Feature tests are marked as having failures
- **Severity**: Medium 
- **Notes**: While the service tests are now passing, additional work is needed on the feature tests

### 3. Integration Tests Failures
- **Files**: Various integration test files
- **Error**: The integration tests are showing failures or warnings
- **Cause**: Similar to feature tests, a mix of Redis and database connection issues
- **Impact**: Integration tests are marked as having failures
- **Severity**: Medium
- **Notes**: Need to investigate the specific failures in integration tests now that the database connection is working correctly

### 4. Deal Analysis Service Calculation Errors
- **Files**: `backend/core/services/deal_analysis.py`
- **Error**: Several division by zero errors and type errors in calculations
- **Cause**: Missing error handling for edge cases like empty data sets and incorrect type conversions
- **Impact**: Error logs but tests still pass due to proper exception handling
- **Severity**: Low (errors are caught and don't cause test failures)
- **Possible Fixes**:
  1. Add proper checks before division operations
  2. Ensure consistent data types in calculations, especially between Decimal and float
  3. Implement proper fallback values when expected data is missing 