# Testing Guide

## Overview

This document outlines the testing strategy and procedures for the AI Agentic Deals System.

## Test Environment

The system uses a dedicated test environment configuration defined in `.env.test`. This environment is separate from development and production to ensure test isolation.

### Test Environment Configuration

The test environment uses:
- Database name: `deals_test`
- Database host: `localhost`
- Redis host: `localhost`
- Debug mode: enabled
- Mock API keys for testing

To set up the test environment:

1. Copy the example environment file:
   ```bash
   cp .env.example .env.test
   ```

2. Update the values for testing:
   ```env
   ENVIRONMENT=test
   DEBUG=true
   POSTGRES_DB=deals_test
   POSTGRES_HOST=localhost
   REDIS_HOST=localhost
   ```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Fast execution
- Located in `tests/unit/`

### Integration Tests
- Test interactions between components
- May use test containers
- Located in `tests/integration/`

### End-to-End Tests
- Test complete workflows
- Simulate user interactions
- Located in `tests/e2e/`

## Test Organization

Tests are organized to match the source code structure:

```
tests/
  ├── unit/
  │   ├── api/
  │   ├── models/
  │   ├── services/
  │   └── utils/
  ├── integration/
  │   ├── api/
  │   ├── database/
  │   └── services/
  └── e2e/
      ├── api/
      └── workflows/
```

## Test Execution

### Running All Tests
```bash
pytest
```

### Running Specific Test Categories
```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# End-to-end tests
pytest tests/e2e
```

### Running Tests with Coverage
```bash
pytest --cov=core
```

## Test Configuration

The test configuration is defined in `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (run first)
    integration: Integration tests (run second)
    e2e: End-to-end tests (run last)
```

## Test Database

Tests use a dedicated test database:

1. The database is created automatically during test setup
2. Each test runs in a transaction that is rolled back after the test
3. The database is cleaned up after all tests are complete

## Test Fixtures

Common test fixtures are defined in `conftest.py`:

```python
@pytest.fixture(scope="session")
async def db():
    """Create a test database and return a session."""
    # Set up test database
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Yield a session
    async with db_session() as session:
        yield session
    
    # Clean up test database
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

## Mock LLM for Testing

Tests use a mock LLM implementation to avoid external API calls:

```python
@pytest.fixture
def mock_llm():
    """Return a mock LLM for testing."""
    return MockLLM()
```

## Test Data

Test data is created using factory patterns:

```python
@pytest.fixture
def user_factory():
    """Factory for creating test users."""
    def _create_user(email="test@example.com", name="Test User"):
        return User(email=email, name=name)
    return _create_user
```

## Test Isolation

Each test is isolated to prevent interference:

1. Database transactions are rolled back after each test
2. Redis data is flushed after each test
3. External services are mocked

## Continuous Integration

Tests are run automatically in the CI/CD pipeline:

1. Unit tests run on every commit
2. Integration tests run on pull requests
3. End-to-end tests run before deployment

## Test Coverage

The project aims for high test coverage:

- Unit tests: 90%+ coverage
- Integration tests: 80%+ coverage
- End-to-end tests: Cover all critical paths

## Testing Best Practices

1. Write tests before implementation (TDD)
2. Keep tests small and focused
3. Use descriptive test names
4. Avoid test interdependence
5. Mock external dependencies
6. Test edge cases and error conditions
7. Maintain test documentation

## Troubleshooting Tests

### Database Connection Issues
1. Verify test database configuration in `.env.test`
2. Check that PostgreSQL is running
3. Ensure the test database exists

### Redis Connection Issues
1. Verify Redis configuration in `.env.test`
2. Check that Redis is running
3. Ensure Redis is accessible

### Mock Configuration Issues
1. Verify mock implementations
2. Check that all external services are properly mocked
3. Ensure test environment is properly isolated

## References

- [pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/session_basics.html#session-frequently-asked-questions)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/) 