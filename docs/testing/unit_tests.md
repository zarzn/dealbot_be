# Unit Testing Guide

## Overview

This document provides detailed guidance for implementing unit tests in the AI Agentic Deals System. Unit testing is a critical practice where individual components are tested in isolation to ensure they work as expected. This guide covers the technical aspects, best practices, and example implementations for unit testing across different system components.

## Unit Testing Framework

The AI Agentic Deals System uses pytest as the primary unit testing framework along with several extensions:

```python
# Required dependencies for testing (from requirements-dev.txt)
pytest==7.3.1
pytest-asyncio==0.21.0
pytest-cov==4.1.0
pytest-mock==3.10.0
pytest-xdist==3.2.1
factory-boy==3.2.1
```

### Key Features

- **pytest-asyncio**: For testing asynchronous code
- **pytest-cov**: For generating code coverage reports
- **pytest-mock**: For mocking dependencies
- **pytest-xdist**: For parallel test execution
- **factory-boy**: For test data generation

## Directory Structure

Unit tests are organized to mirror the structure of the source code:

```
backend/
├── core/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── ...
└── tests/
    └── unit/
        ├── api/
        ├── models/
        ├── services/
        └── ...
```

Each unit test file should correspond to a source file with the same name, prefixed with `test_`:

- Source file: `core/services/auth.py`
- Test file: `tests/unit/services/test_auth.py`

## Unit Test Anatomy

A well-structured unit test should include these elements:

1. **Imports**: Required modules, including the component under test
2. **Fixtures**: Test data and dependencies setup
3. **Test cases**: Individual test functions grouped by functionality
4. **Mocks/Stubs**: Isolation of external dependencies
5. **Assertions**: Verification of expected behavior

### Example Test Structure

```python
# tests/unit/services/test_auth.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.services.auth import AuthService
from core.models.users import User
from core.exceptions import AuthenticationError


@pytest.fixture
def auth_service():
    """Fixture providing a configured AuthService instance."""
    return AuthService()


@pytest.fixture
def mock_user_service():
    """Fixture providing a mocked UserService."""
    with patch("core.services.auth.UserService") as mock:
        mock_instance = mock.return_value
        mock_instance.get_user_by_email.return_value = User(
            id=1,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True
        )
        yield mock_instance


class TestAuthService:
    """Tests for the AuthService."""

    async def test_authenticate_user_success(self, auth_service, mock_user_service):
        """Test successful user authentication."""
        # Arrange
        email = "test@example.com"
        password = "password123"
        
        with patch("core.services.auth.verify_password", return_value=True):
            # Act
            user = await auth_service.authenticate_user(email, password)
            
            # Assert
            assert user is not None
            assert user.email == email
            mock_user_service.get_user_by_email.assert_called_once_with(email)

    async def test_authenticate_user_invalid_credentials(self, auth_service, mock_user_service):
        """Test authentication with invalid credentials."""
        # Arrange
        email = "test@example.com"
        password = "wrong_password"
        
        with patch("core.services.auth.verify_password", return_value=False):
            # Act & Assert
            with pytest.raises(AuthenticationError) as exc_info:
                await auth_service.authenticate_user(email, password)
            
            assert "Invalid credentials" in str(exc_info.value)
```

## Testing Different Component Types

### 1. Testing Services

Services often contain complex business logic and interact with multiple dependencies:

```python
# tests/unit/services/test_token_service.py
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from core.services.token import TokenService
from core.exceptions import InsufficientTokensError


@pytest.fixture
def token_service():
    with patch("core.services.token.get_redis_service") as mock_redis_factory:
        mock_redis = MagicMock()
        mock_redis_factory.return_value = mock_redis
        
        with patch("core.services.token.get_db_session") as mock_db_session:
            service = TokenService()
            yield service


class TestTokenService:
    
    async def test_deduct_tokens_sufficient_balance(self, token_service):
        # Arrange
        user_id = "user123"
        amount = Decimal("10.0")
        token_service._get_user_balance = MagicMock(return_value=Decimal("50.0"))
        token_service._update_user_balance = MagicMock()
        token_service._record_transaction = MagicMock()
        
        # Act
        result = await token_service.deduct_tokens(user_id, amount, "service_fee")
        
        # Assert
        assert result is True
        token_service._get_user_balance.assert_called_once_with(user_id)
        token_service._update_user_balance.assert_called_once_with(
            user_id, Decimal("40.0")
        )
        token_service._record_transaction.assert_called_once()
    
    async def test_deduct_tokens_insufficient_balance(self, token_service):
        # Arrange
        user_id = "user123"
        amount = Decimal("60.0")
        token_service._get_user_balance = MagicMock(return_value=Decimal("50.0"))
        
        # Act & Assert
        with pytest.raises(InsufficientTokensError):
            await token_service.deduct_tokens(user_id, amount, "service_fee")
```

### 2. Testing Models

Models should be tested for validation, relationships, and methods:

```python
# tests/unit/models/test_deal.py
import pytest
from datetime import datetime, timedelta

from core.models.deals import Deal, DealStatus
from core.exceptions import ValidationError


class TestDealModel:

    def test_deal_expiration_validation(self):
        # Arrange
        past_date = datetime.utcnow() - timedelta(days=1)
        
        # Act & Assert
        with pytest.raises(ValidationError):
            Deal(
                title="Test Deal",
                description="Test Description",
                price=99.99,
                original_price=149.99,
                url="https://example.com/deal",
                source="amazon",
                expires_at=past_date,
                status=DealStatus.ACTIVE
            )
    
    def test_calculate_savings(self):
        # Arrange
        deal = Deal(
            title="Test Deal",
            description="Test Description",
            price=80.0,
            original_price=100.0,
            url="https://example.com/deal",
            source="amazon",
            expires_at=datetime.utcnow() + timedelta(days=7),
            status=DealStatus.ACTIVE
        )
        
        # Act
        savings = deal.calculate_savings()
        savings_percentage = deal.calculate_savings_percentage()
        
        # Assert
        assert savings == 20.0
        assert savings_percentage == 20.0
```

### 3. Testing API Endpoints

API endpoints should be tested using FastAPI's test client:

```python
# tests/unit/api/test_deals_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from core.models.deals import Deal, DealStatus
from core.api.dependencies import get_current_user


# Override dependency to provide a test user
@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test_user_id",
        "email": "test@example.com",
        "is_active": True
    }
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = {}


class TestDealsAPI:

    def test_get_deals(self, client):
        # Arrange
        mock_deals = [
            Deal(
                id="deal1",
                title="Deal 1",
                description="Description 1",
                price=99.99,
                original_price=149.99,
                url="https://example.com/deal1",
                source="amazon",
                status=DealStatus.ACTIVE
            ),
            Deal(
                id="deal2",
                title="Deal 2",
                description="Description 2",
                price=199.99,
                original_price=249.99,
                url="https://example.com/deal2",
                source="walmart",
                status=DealStatus.ACTIVE
            )
        ]
        
        with patch("core.api.endpoints.deals.get_deal_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.get_deals.return_value = mock_deals
            
            # Act
            response = client.get("/api/deals/")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["title"] == "Deal 1"
            assert data[1]["title"] == "Deal 2"
```

### 4. Testing AI Agents

AI agents require specialized testing approaches:

```python
# tests/unit/agents/test_deal_analysis_agent.py
import pytest
from unittest.mock import patch, MagicMock

from core.agents.deal_analysis import DealAnalysisAgent
from core.models.enums import MarketType


class TestDealAnalysisAgent:

    @pytest.fixture
    def agent(self):
        with patch("core.agents.deal_analysis.get_llm_service") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance
            agent = DealAnalysisAgent()
            yield agent

    async def test_analyze_deal_good_value(self, agent):
        # Arrange
        deal_data = {
            "title": "Sony WH-1000XM4 Wireless Noise Cancelling Headphones",
            "price": 248.0,
            "original_price": 349.99,
            "description": "Industry-leading noise cancellation, 30-hour battery life",
            "source": "amazon",
            "category": "electronics",
            "subcategory": "headphones"
        }
        
        mock_response = {
            "deal_quality": "high",
            "value_assessment": 8.5,
            "price_analysis": "This is a historic low price for this model.",
            "recommendations": ["This deal is recommended for audiophiles and frequent travelers."]
        }
        
        agent._llm_service.analyze_text.return_value = mock_response
        
        # Act
        result = await agent.analyze_deal(deal_data, MarketType.ELECTRONICS)
        
        # Assert
        assert result["deal_quality"] == "high"
        assert result["value_assessment"] == 8.5
        agent._llm_service.analyze_text.assert_called_once()
        
    async def test_analyze_deal_with_backup_model(self, agent):
        # Arrange
        deal_data = {
            "title": "Samsung 65-inch 4K Smart TV",
            "price": 599.99,
            "original_price": 799.99,
            "description": "Crystal UHD, HDR, Smart TV features",
            "source": "bestbuy",
            "category": "electronics",
            "subcategory": "televisions"
        }
        
        # Primary model fails
        agent._llm_service.analyze_text.side_effect = [
            Exception("Rate limit exceeded"),  # First call fails
            {  # Second call (backup model) succeeds
                "deal_quality": "medium",
                "value_assessment": 6.5,
                "price_analysis": "Good price but not exceptional.",
                "recommendations": ["Consider waiting for holiday sales for better pricing."]
            }
        ]
        
        # Act
        result = await agent.analyze_deal(deal_data, MarketType.ELECTRONICS)
        
        # Assert
        assert result["deal_quality"] == "medium"
        assert result["value_assessment"] == 6.5
        assert agent._llm_service.analyze_text.call_count == 2
```

## Mocking and Dependency Injection

### Mocking Database Access

```python
# Example of mocking database access
@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    
    with patch("core.database.get_db_session", return_value=mock_session):
        yield mock_session
```

### Mocking External Services

```python
# Example of mocking external service
@pytest.fixture
def mock_payment_gateway():
    """Mock payment gateway for testing."""
    with patch("core.services.payment.PaymentGateway") as mock:
        mock_instance = mock.return_value
        mock_instance.process_payment.return_value = {
            "status": "success",
            "transaction_id": "txn_123456",
            "amount": 99.99
        }
        yield mock_instance
```

### Mocking Redis

```python
# Example of mocking Redis
@pytest.fixture
def mock_redis():
    """Mock Redis for testing."""
    with patch("core.services.redis.get_redis_client") as mock:
        mock_instance = mock.return_value
        mock_instance.get.return_value = "cached_value"
        mock_instance.setex.return_value = True
        yield mock_instance
```

## Testing Asynchronous Code

The system makes extensive use of asynchronous programming. Here's how to test async code:

```python
# Example of testing async code
import pytest

@pytest.mark.asyncio
async def test_async_function():
    # Arrange
    service = AsyncService()
    
    # Act
    result = await service.process_data()
    
    # Assert
    assert result == expected_result
```

### Handling Async Context Managers

```python
# Testing code that uses async context managers
@pytest.mark.asyncio
async def test_with_async_context_manager():
    # Mocking an async context manager
    mock_cm = MagicMock()
    mock_cm.__aenter__.return_value = mock_cm
    mock_cm.__aexit__.return_value = None
    mock_cm.execute.return_value = "result"
    
    with patch("module.AsyncContextManager", return_value=mock_cm):
        # Act
        service = Service()
        result = await service.method_using_context_manager()
        
        # Assert
        assert result == "result"
        mock_cm.__aenter__.assert_called_once()
        mock_cm.execute.assert_called_once()
        mock_cm.__aexit__.assert_called_once()
```

## Testing Error Handling

Proper error handling is critical. Test both success and failure paths:

```python
# Example of testing error handling
@pytest.mark.asyncio
async def test_service_handles_dependency_error():
    # Arrange
    service = Service()
    with patch("module.dependency_function", side_effect=DependencyError("Failed")):
        
        # Act
        with pytest.raises(ServiceError) as exc_info:
            await service.method()
        
        # Assert
        assert "Service unavailable" in str(exc_info.value)
        assert exc_info.value.status_code == 503
```

## Parameterized Tests

Use parameterized tests to reduce duplication and test multiple scenarios:

```python
# Example of parameterized tests
import pytest

@pytest.mark.parametrize(
    "input_value,expected_result",
    [
        ("valid_input", True),
        ("invalid_input", False),
        ("", False),
        (None, False),
    ],
)
def test_validator(input_value, expected_result):
    validator = Validator()
    result = validator.is_valid(input_value)
    assert result == expected_result
```

## Testing with Factories

Use factories to create test data:

```python
# Example factory for User model
import factory
from core.models.users import User

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    id = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Faker("name")
    hashed_password = "hashed_password"
    is_active = True
    created_at = factory.LazyFunction(lambda: datetime.utcnow())
```

Using the factory in tests:

```python
def test_user_service_with_factory(mock_db_session):
    # Arrange
    users = [UserFactory() for _ in range(5)]
    mock_db_session.query().filter().all.return_value = users
    
    # Act
    service = UserService()
    result = service.get_active_users()
    
    # Assert
    assert len(result) == 5
```

## Code Coverage

Unit tests should aim for high code coverage, particularly for critical paths:

```bash
# Run tests with coverage
pytest tests/unit/ --cov=core --cov-report=term --cov-report=html
```

Coverage targets:
- Core business logic: 90%+
- Service layer: 80%+
- Models: 80%+
- API endpoints: 80%+
- Utility functions: 70%+

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests.

2. **Fast Execution**: Unit tests should execute quickly (under 100ms per test).

3. **Clear Purpose**: Each test should have a clear purpose and test a single aspect of behavior.

4. **Descriptive Names**: Test methods should have descriptive names that indicate what is being tested.

5. **Arrange-Act-Assert**: Structure tests using the AAA pattern:
   - Arrange: Set up the test data and conditions
   - Act: Perform the action being tested
   - Assert: Verify the results

6. **Test Edge Cases**: Test boundary conditions and error cases:
   - Empty inputs
   - Maximum/minimum values
   - Invalid inputs
   - Resource unavailability

7. **Avoid Test Logic**: Keep test code simple and avoid complex conditionals.

8. **Clean Test Data**: Clean up test data and resources after each test.

9. **Test Public Interfaces**: Focus on testing public interfaces, not implementation details.

10. **Updated Tests**: Keep tests updated when code changes.

## Common Anti-Patterns to Avoid

1. **Testing Implementation Details**: Test behavior, not implementation details.

2. **Overcomplicated Test Setup**: Keep test setup concise and focused.

3. **Interdependent Tests**: Tests should not depend on each other's execution or results.

4. **Slow Tests**: Unit tests should be fast; move slow operations to integration tests.

5. **Overmocking**: Don't mock everything; sometimes it's better to use real objects.

6. **Brittle Tests**: Tests should not break with minor code changes.

7. **Incomplete Assertions**: Assert all relevant aspects of the result.

8. **Test Code Duplication**: Use fixtures and helpers to reduce duplication.

## Running Tests

### Running All Unit Tests

```bash
pytest tests/unit/
```

### Running Tests for a Specific Module

```bash
pytest tests/unit/services/test_auth.py
```

### Running a Specific Test

```bash
pytest tests/unit/services/test_auth.py::TestAuthService::test_authenticate_user_success
```

### Running Tests with JUnit Report (for CI)

```bash
pytest tests/unit/ --junitxml=reports/unit-tests.xml
```

## CI/CD Integration

Unit tests are automatically run as part of the CI/CD pipeline:

1. **Pre-Commit Hook**: Basic tests run before commit
2. **Pull Request Validation**: All unit tests run when creating a PR
3. **Main Branch Protection**: PRs require passing unit tests
4. **Nightly Builds**: Full test suite with coverage report

## Troubleshooting Common Issues

### Tests Hanging

Possible causes:
- Uncompleted async operations
- Unresolved promises
- Infinite loops

Solution: Add timeouts to your tests:

```python
@pytest.mark.asyncio
@pytest.mark.timeout(2)  # 2-second timeout
async def test_with_timeout():
    # Test code here
```

### Tests Failing in CI but Passing Locally

Possible causes:
- Environment differences
- Timing issues
- Resource constraints

Solution: Make tests more robust to environment changes and add logging.

### Flaky Tests

Possible causes:
- Race conditions
- Time dependencies
- External services

Solution: Identify and fix the root cause, not just retry the test.

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)
- [Python unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html) 