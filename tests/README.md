# Test Suite Documentation

## Overview
This test suite provides comprehensive testing for the AI Agentic Deals System. It includes unit tests, integration tests, and end-to-end tests for all major components of the system.

## Running Tests

### Full Test Suite
To run the complete test suite with detailed reporting:
```powershell
./scripts/run_tests.ps1
```

This will:
- Run all tests in each test directory
- Generate an HTML report in `test_results/`
- Show a summary of passed/failed tests
- Exit with the number of failed tests (0 if all passed)

### Test Categories
Tests are organized into the following categories:
- `test_api/`: API endpoint tests
- `test_agents/`: Agent system tests
- `test_cache/`: Cache functionality tests
- `test_integration/`: Integration tests
- `test_models/`: Database model tests
- `test_tasks/`: Background task tests
- `test_websockets/`: WebSocket tests

### Running Specific Tests
To run tests from a specific category:
```powershell
python -m pytest tests/test_api -v
```

To run a specific test file:
```powershell
python -m pytest tests/test_cache/test_redis.py -v
```

### Test Markers
Available pytest markers:
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.api`: API tests
- `@pytest.mark.slow`: Slow tests
- `@pytest.mark.redis`: Redis-dependent tests
- `@pytest.mark.websocket`: WebSocket tests
- `@pytest.mark.scraper`: Scraper tests
- `@pytest.mark.agent`: Agent tests

To run tests with a specific marker:
```powershell
python -m pytest -m "redis" -v
```

## Test Results
Test results are stored in the `test_results/` directory:
- HTML report: `test_report.html`
- XML reports: `{category}-results.xml`

## Debugging Failed Tests
When tests fail, the report will show:
- The exact test that failed
- The failure reason
- Local variables at the point of failure
- The full traceback

## Best Practices
1. Run the full test suite before pushing changes
2. Add appropriate markers to new tests
3. Keep tests focused and independent
4. Use meaningful test names
5. Add proper docstrings to test functions
6. Clean up test data in teardown

## Common Issues and Solutions
1. **Database Connection Issues**
   - Ensure PostgreSQL is running
   - Check database credentials in test config

2. **Redis Connection Issues**
   - Ensure Redis is running
   - Check Redis connection settings

3. **Timeout Issues**
   - Check the `timeout` setting in `pytest.ini`
   - Mark slow tests with `@pytest.mark.slow`

4. **WebSocket Test Failures**
   - Ensure ports are not in use
   - Check WebSocket server configuration

## Adding New Tests
1. Create test files in appropriate directories
2. Use proper naming convention (`test_*.py`)
3. Add appropriate markers
4. Update test documentation if needed
5. Ensure independence from other tests 