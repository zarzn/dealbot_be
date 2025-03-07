# Testing Guide for AI Agentic Deals System

This comprehensive guide outlines the testing strategy, organization, and best practices for the AI Agentic Deals System.

## Table of Contents
1. [Test Environment Setup](#test-environment-setup)
2. [Test Organization](#test-organization)
3. [Test Categories](#test-categories)
4. [Writing Effective Tests](#writing-effective-tests)
5. [Test Data Management](#test-data-management)
6. [Running Tests](#running-tests)
7. [Continuous Integration](#continuous-integration)
8. [Test Coverage](#test-coverage)
9. [Troubleshooting](#troubleshooting)

## Test Environment Setup

### Environment Configuration

The test environment is defined in `.env.test` and is separate from development and production environments. Key configurations include:

```
# Application Settings
ENVIRONMENT=test
DEBUG=true

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=agentic_deals_test
POSTGRES_HOST=localhost

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# API Keys
DEEPSEEK_API_KEY=mock_deepseek_key_for_testing
OPENAI_API_KEY=mock_openai_key_for_testing

# LLM Configuration
LLM_PROVIDER=mock
```

### Setup Instructions

1. **Copy Environment File**:
   ```bash
   cp backend/.env.test.example backend/.env.test
   ```

2. **Update Values**:
   - Set database credentials appropriate for your test environment
   - Use mock API keys for external services
   - Configure environment-specific settings

3. **Database Setup**:
   ```bash
   python backend/scripts/setup_test_db.py
   ```
   This script creates a clean test database with the necessary schema.

4. **Mock External Services**:
   - Configure all external services to use mock implementations for testing
   - Set up test doubles for all third-party dependencies

## Test Organization

### Directory Structure

The tests are organized as follows:

```
backend_tests/
├── conftest.py              # Shared fixtures
├── core/                    # Core unit tests
│   ├── models/              # Database model tests
│   ├── utils/               # Utility function tests
│   └── services/            # Core service tests
├── api/                     # API tests
│   ├── v1/                  # API v1 endpoint tests
│   └── middleware/          # Middleware tests
├── services/                # Service layer tests
│   ├── auth/                # Authentication service tests
│   ├── deals/               # Deal service tests
│   └── ai/                  # AI service tests
├── features/                # Feature-level tests
│   ├── deal_search/         # Deal search feature tests
│   ├── analysis/            # Analysis feature tests
│   └── user_management/     # User management tests
└── integration/             # Integration tests
    ├── database/            # Database integration tests
    ├── redis/               # Redis integration tests
    ├── api/                 # Full API integration tests
    └── external/            # External service integration tests
```

### Test Categories

#### 1. Core Tests
Basic unit tests for core functionality located in `backend_tests/core/`. These tests focus on individual components and functions without external dependencies.

#### 2. Service Tests
Tests for the service layer located in `backend_tests/services/`. These tests focus on business logic and may include mock external dependencies.

#### 3. Feature Tests
Tests for complete features located in `backend_tests/features/`. These tests focus on end-to-end feature functionality.

#### 4. Integration Tests
Tests for API and system integration located in `backend_tests/integration/`. These tests focus on how different components work together.

### Test File Naming

- Test files should be named with `test_` prefix
- Test files should match the name of the module they test
- Test classes should be named with `Test` prefix
- Test methods should be named with `test_` prefix

Example:
```python
# Module: backend/core/services/deals.py
# Test file: backend_tests/core/services/test_deals.py

class TestDealService:
    def test_create_deal(self):
        # Test code
    
    def test_update_deal(self):
        # Test code
```

## Test Categories

### Unit Tests

Unit tests focus on testing individual components in isolation. They should:

1. Test a single function, method, or class
2. Mock all external dependencies
3. Be fast and independent
4. Cover edge cases and error conditions

Example unit test:
```python
def test_validate_market_type():
    # Valid case
    assert validate_market_type(MarketType.TEST.value) == MarketType.TEST
    
    # Invalid case
    with pytest.raises(ValueError):
        validate_market_type("invalid_market")
```

### Integration Tests

Integration tests verify that different components work together correctly. They should:

1. Test interactions between multiple components
2. Use test databases and mock external APIs
3. Verify correct data flow between components
4. Test transaction boundaries and rollback behavior

Example integration test:
```python
@pytest.mark.asyncio
async def test_create_deal_with_market(db_session):
    # Create market first
    market = await MarketService.create_market(
        name="Test Market",
        type=MarketType.TEST.value
    )
    
    # Create deal with market reference
    deal = await DealService.create_deal(
        title="Test Deal",
        description="Test Description",
        market_id=market.id
    )
    
    # Verify relationship
    assert deal.market_id == market.id
    
    # Clean up
    await DealService.delete_deal(deal.id)
    await MarketService.delete_market(market.id)
```

### API Tests

API tests verify the behavior of API endpoints. They should:

1. Test HTTP endpoints and status codes
2. Verify request validation
3. Test authentication and authorization
4. Check response format and content

Example API test:
```python
@pytest.mark.asyncio
async def test_get_deal_endpoint(client, test_deal):
    response = await client.get(f"/api/v1/deals/{test_deal.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_deal.id)
    assert data["title"] == test_deal.title
```

### End-to-End Tests

End-to-end tests verify complete user workflows. They should:

1. Test full user scenarios from start to finish
2. Use a complete test environment
3. Minimize mocking where possible
4. Verify system behavior as a whole

Example E2E test:
```python
@pytest.mark.asyncio
async def test_deal_search_and_analysis(authenticated_client, setup_test_deals):
    # Search for deals
    search_response = await authenticated_client.get("/api/v1/deals/search?query=test")
    assert search_response.status_code == 200
    deals = search_response.json()["results"]
    assert len(deals) > 0
    
    # Select a deal for analysis
    deal_id = deals[0]["id"]
    
    # Request analysis
    analysis_response = await authenticated_client.post(
        "/api/v1/analysis",
        json={"deal_ids": [deal_id]}
    )
    assert analysis_response.status_code == 202
    task_id = analysis_response.json()["task_id"]
    
    # Poll for results
    max_attempts = 10
    for attempt in range(max_attempts):
        result_response = await authenticated_client.get(f"/api/v1/analysis/tasks/{task_id}")
        if result_response.json()["status"] == "completed":
            break
        await asyncio.sleep(1)
    
    # Verify analysis results
    assert result_response.status_code == 200
    results = result_response.json()
    assert results["status"] == "completed"
    assert deal_id in results["results"]
    assert "score" in results["results"][deal_id]
```

## Writing Effective Tests

### Test Case Design

Follow these principles for designing test cases:

1. **ARANGE-ACT-ASSERT Pattern**:
   - Arrange: Set up test preconditions
   - Act: Perform the action being tested
   - Assert: Verify the expected outcome

2. **Use Descriptive Test Names**:
   - Test names should describe what is being tested
   - Include the expected behavior in the name
   - Use a consistent naming convention

3. **Test One Thing Per Test**:
   - Each test should verify a single behavior
   - Avoid testing multiple behaviors in one test
   - Split complex tests into multiple smaller tests

4. **Cover Edge Cases**:
   - Test boundary conditions
   - Test error cases and exceptions
   - Test empty/null inputs and special character handling

### Testing Async Code

Most of the backend code is asynchronous, so tests should use the appropriate async testing tools:

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    # Arrange
    input_data = {"key": "value"}
    
    # Act
    result = await async_function(input_data)
    
    # Assert
    assert result["processed"] == True
```

### Testing Database Code

For database tests, use the SQLAlchemy test fixtures:

```python
@pytest.mark.asyncio
async def test_create_user(db_session):
    # Arrange
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "password": "securepassword"
    }
    
    # Act
    user = await UserService.create_user(**user_data)
    
    # Assert
    assert user.id is not None
    assert user.email == user_data["email"]
    assert user.name == user_data["name"]
    assert verify_password(user_data["password"], user.password_hash)
```

### Testing with Enums

When working with enums in tests:

1. Always use `.value` when comparing enum values
2. Verify that enum values are stored correctly in the database
3. Test invalid enum values handling

Example:
```python
def test_market_type_enum():
    # Create with valid enum value
    market = MarketFactory(type=MarketType.TEST.value)
    assert market.type == MarketType.TEST.value
    
    # Test validation
    with pytest.raises(ValueError):
        MarketFactory(type="invalid_type")
```

## Test Data Management

### Test Fixtures

Use pytest fixtures for setting up test data:

```python
@pytest.fixture
def test_user():
    """Create a test user for testing."""
    return UserFactory()

@pytest.fixture
def test_deal(test_user):
    """Create a test deal with owner."""
    return DealFactory(owner_id=test_user.id)

@pytest.fixture
async def authenticated_client(client, test_user):
    """Return an authenticated client."""
    credentials = {
        "email": test_user.email,
        "password": "testpassword"
    }
    response = await client.post("/api/v1/auth/login", json=credentials)
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
```

### Test Factories

Use factory_boy to create test data:

```python
# backend_tests/factories/user_factory.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from core.models.user import User
from core.utils.security import get_password_hash

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = None  # Set in fixtures
    
    id = factory.Sequence(lambda n: n)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Sequence(lambda n: f"User {n}")
    password_hash = factory.LazyFunction(lambda: get_password_hash("testpassword"))
    is_active = True
```

### Database Reset

Ensure tests don't interfere with each other by resetting the database state:

```python
@pytest.fixture(scope="function")
async def db_session():
    """Create a clean database session for a test."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)
    
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
```

## Running Tests

### Running All Tests

To run the complete test suite:

```bash
# Windows PowerShell
.\backend\scripts\dev\test\run_patched_tests.ps1

# Alternative
cd backend
pytest
```

### Running Specific Tests

To run specific test categories:

```bash
# Run unit tests only
pytest backend_tests/core/

# Run tests for a specific module
pytest backend_tests/services/deals/

# Run tests matching a pattern
pytest -k "market or deal"

# Run a specific test file
pytest backend_tests/api/v1/test_deals.py

# Run a specific test
pytest backend_tests/api/v1/test_deals.py::test_create_deal
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.slow
def test_slow_operation():
    # This test takes a long time to run
    ...

@pytest.mark.requires_external_api
def test_external_service():
    # This test requires an external API
    ...
```

To run tests with specific markers:

```bash
# Run only slow tests
pytest -m slow

# Run all tests except slow ones
pytest -m "not slow"
```

## Continuous Integration

### CI Pipeline Configuration

The CI pipeline is configured to run tests automatically on code changes:

1. **Pre-commit Hooks**: Run basic validation and linting
2. **Pull Request Checks**: Run unit and integration tests
3. **Merge Checks**: Run the complete test suite
4. **Nightly Tests**: Run long-running and performance tests

### Test Execution Order

Tests are executed in the following order:

1. Unit tests (fast, no external dependencies)
2. Integration tests (may require test containers)
3. API tests (require full test environment)
4. End-to-end tests (complete system tests)

### Test Failure Handling

When tests fail in CI:

1. Examine test logs to understand the cause
2. Check if failures are related to recent changes
3. Verify if test environment is correctly configured
4. Fix issues and re-run tests
5. For flaky tests, mark them for review and improvement

## Test Coverage

### Coverage Goals

The project aims for the following test coverage targets:

- Core business logic: 95%+
- API endpoints: 90%+
- Service layer: 90%+
- Utility functions: 85%+
- UI components: 80%+

### Measuring Coverage

To measure test coverage:

```bash
# Generate coverage report
pytest --cov=backend --cov-report=html

# View report
# Open htmlcov/index.html in a browser
```

### Coverage Requirements

For new code:
- Pull requests should not decrease overall coverage
- New features should include tests with at least 85% coverage
- Bug fixes should include regression tests

## Troubleshooting

### Common Test Issues

1. **Database Conflicts**:
   - Ensure tests clean up created data
   - Use transaction rollback for test isolation
   - Reset sequences between test runs

2. **Async Test Problems**:
   - Use the correct async test decorators
   - Handle event loops properly
   - Close all connections and resources

3. **Test Data Issues**:
   - Use factories with random/unique data
   - Avoid hardcoded IDs or timestamps
   - Don't rely on specific database state

4. **Slow Tests**:
   - Mock external services
   - Use in-memory databases where possible
   - Mark slow tests and run them separately

### Duplicate Tests

Avoid duplicate tests by:

1. **Centralizing Common Test Logic**:
   - Use test fixtures for common setup
   - Create helper functions for repeated assertions
   - Use parametrized tests for similar test cases

2. **Organizing Tests Hierarchically**:
   - Unit tests for individual functions
   - Integration tests for combinations of components
   - Feature tests for end-to-end functionality

3. **Clear Test Purpose**:
   - Each test should have a clear and distinct purpose
   - Document why each test exists
   - Regularly review tests for redundancy

### Flaky Tests

For tests that fail intermittently:

1. **Identify Root Causes**:
   - Timing issues (add appropriate waits)
   - Resource conflicts (improve isolation)
   - External dependencies (better mocking)

2. **Improve Stability**:
   - Add retry mechanisms for flaky operations
   - Improve assertions to be more robust
   - Add better error handling and diagnostics

3. **Temporary Handling**:
   - Mark flaky tests with `@pytest.mark.flaky`
   - Document known issues
   - Set up automatic retry for flaky tests 