# New Test Suite Structure

## Overview
This is a new, organized test suite that implements dependency tracking and ensures tests don't break each other.

## Directory Structure
```
new_suite/
├── core/                 # Core functionality tests (Level 1)
│   ├── test_models/     # Database model tests
│   ├── test_auth/       # Authentication tests
│   └── test_redis/      # Redis core tests
├── services/            # Service layer tests (Level 2)
│   ├── test_user/       # User service tests
│   ├── test_goal/       # Goal service tests
│   ├── test_deal/       # Deal service tests
│   └── test_token/      # Token service tests
├── features/            # Feature tests (Level 3)
│   ├── test_goals/      # Goal feature tests
│   ├── test_deals/      # Deal feature tests
│   └── test_agents/     # Agent feature tests
├── integration/         # Integration tests (Level 4)
│   ├── test_api/        # API integration tests
│   ├── test_websocket/  # WebSocket integration tests
│   └── test_workflows/  # Full workflow tests
├── factories/           # Test factories
│   ├── base.py         # Base factory class
│   ├── user.py         # User factory
│   ├── goal.py         # Goal factory
│   └── deal.py         # Deal factory
├── utils/              # Test utilities
│   ├── state.py        # Test state management
│   ├── dependencies.py # Dependency tracking
│   └── markers.py      # Test markers
├── conftest.py         # Test configuration and fixtures
└── pytest.ini          # PyTest configuration
```

## Test Execution
Tests are executed in the following order:

1. Core Tests (Level 1)
   ```powershell
   pytest new_suite/core -v
   ```

2. Service Tests (Level 2)
   ```powershell
   pytest new_suite/services -v
   ```

3. Feature Tests (Level 3)
   ```powershell
   pytest new_suite/features -v
   ```

4. Integration Tests (Level 4)
   ```powershell
   pytest new_suite/integration -v
   ```

## Test Dependencies
Dependencies are tracked in `utils/dependencies.py`:

```python
DEPENDENCIES = {
    'user_service': ['auth_core', 'db_models'],
    'goal_service': ['user_service', 'db_models'],
    'deal_service': ['goal_service', 'market_service'],
    'token_service': ['user_service', 'redis_core']
}
```

## Test Factories
Factories are used to create consistent test data:

```python
from factories.user import UserFactory
from factories.goal import GoalFactory

# Create user with dependencies
user = await UserFactory.create()

# Create goal with user
goal = await GoalFactory.create(user=user)
```

## State Management
Test state is managed to prevent conflicts:

```python
from utils.state import TestStateManager

# Verify dependencies before running tests
state_manager = TestStateManager()
if not state_manager.verify_dependencies('goals'):
    pytest.skip("Dependencies not met")
```

## Running Tests
To run the complete test suite with dependency checking:

```powershell
./scripts/run_new_tests.ps1
```

This will:
1. Run core tests first
2. Only proceed to service tests if core passes
3. Only proceed to feature tests if services pass
4. Only run integration tests if features pass

## Migration from Old Tests
Existing tests are being gradually migrated to this new structure. The process:

1. Identify test dependencies
2. Create appropriate factories
3. Move tests to correct level
4. Add state management
5. Verify isolation

## Best Practices
1. Always use factories for test data
2. Verify dependencies before tests
3. Keep tests isolated
4. Run tests in correct order
5. Use proper markers
6. Clean up test data 