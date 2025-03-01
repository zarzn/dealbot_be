# Testing Documentation

## Overview
The testing suite is designed to ensure the reliability and correctness of the AI Agentic Deals System. It follows a comprehensive testing strategy with different types of tests organized in a clear structure.

## Test Structure
```
backend/backend_tests/
├── core/           # Core functionality tests
├── features/       # Feature-specific tests
├── integration/    # Integration tests
├── services/       # Service layer tests
├── utils/          # Utility function tests
├── factories/      # Test data factories
│   ├── base.py    # Base factory configuration
│   ├── user.py    # User data factory
│   ├── goal.py    # Goal data factory
│   ├── deal.py    # Deal data factory
│   ├── market.py  # Market data factory
│   └── token.py   # Token data factory
└── conftest.py    # Test configuration and fixtures
```

## Test Configuration

### Database Configuration
- Test database uses PostgreSQL with asyncpg driver
- Separate test database: `deals_test`
- Clean database state for each test
- Automatic schema creation and cleanup
- Transaction-based test isolation

### Redis Configuration
- Separate Redis database (DB 1) for testing
- Clean Redis state for each test
- Proper connection pooling and cleanup
- Automatic flush between tests

### Test Client Setup
- FastAPI TestClient integration
- Dependency injection overrides
- Clean application state between tests
- Proper session management

## Test Fixtures

### Database Fixtures
```python
@pytest.fixture(scope="session")
async def test_db():
    # Provides test database engine
    # Handles schema creation and cleanup

@pytest.fixture(scope="function")
async def db_session(test_db):
    # Provides isolated database session
    # Handles transaction management
    # Automatic rollback after each test
```

### Redis Fixtures
```python
@pytest.fixture(scope="function")
async def redis():
    # Provides isolated Redis connection
    # Handles connection management
    # Automatic cleanup after each test
```

### Application Fixtures
```python
@pytest.fixture(scope="function")
async def client(db_session):
    # Provides configured test client
    # Handles dependency overrides
    # Clean state for each test
```

## Test Factories

### Base Factory
- Provides common factory functionality
- Handles session management
- Supports async operations
- Manages sequence generation

### Entity Factories

#### UserFactory
- Creates test user data
- Handles password hashing
- Generates unique emails
- Manages referral codes

#### GoalFactory
- Creates test goal data
- Links to user accounts
- Handles goal constraints
- Manages goal status

#### DealFactory
- Creates test deal data
- Links to goals and markets
- Handles price calculations
- Manages deal status

#### MarketFactory
- Creates test market data
- Handles market types
- Manages API configurations
- Sets rate limits

#### TokenFactory
- Creates test token data
- Handles different token types
- Manages token status
- Sets expiration times

## Test Categories

### Unit Tests
- Located in `core/` and `utils/`
- Test individual components
- No external dependencies
- Fast execution

### Integration Tests
- Located in `integration/`
- Test component interactions
- Use test containers
- Database integration
- Redis integration

### Feature Tests
- Located in `features/`
- Test complete features
- End-to-end workflows
- Business logic validation

### Service Tests
- Located in `services/`
- Test service layer
- External service integration
- API integrations

## Test Execution

### Running Tests
```bash
# Run all tests
pytest backend/backend_tests

# Run specific test categories
pytest backend/backend_tests/core        # Unit tests
pytest backend/backend_tests/integration # Integration tests
pytest backend/backend_tests/features    # Feature tests

# Run with coverage
pytest --cov=backend backend/backend_tests
```

### Test Markers
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.feature`: Feature tests
- `@pytest.mark.slow`: Slow tests
- `@pytest.mark.api`: API tests

## Best Practices

### Test Organization
1. Follow test isolation principle
2. One test file per source file
3. Clear test naming convention
4. Proper use of fixtures
5. Clean state between tests

### Test Data
1. Use factories for test data
2. Avoid hard-coded values
3. Clear data setup and cleanup
4. Realistic test scenarios
5. Handle edge cases

### Assertions
1. Use specific assertions
2. Clear failure messages
3. Check both positive and negative cases
4. Validate state changes
5. Verify side effects

### Performance
1. Fast test execution
2. Proper use of test scopes
3. Efficient database operations
4. Minimal external dependencies
5. Parallel test execution where possible

## CI/CD Integration

### Test Pipeline
1. Run unit tests on every commit
2. Run integration tests on PR
3. Run full suite before deploy
4. Generate coverage reports
5. Enforce minimum coverage

### Quality Gates
1. 100% pass rate required
2. Minimum 80% coverage
3. No new issues in SonarQube
4. Performance benchmarks met
5. All critical paths tested

## Monitoring and Reporting

### Test Reports
- HTML test reports
- Coverage reports
- Performance metrics
- Failure analysis
- Trend monitoring

### Maintenance
1. Regular test suite review
2. Remove obsolete tests
3. Update test data
4. Maintain documentation
5. Monitor test performance 