# Goal Feature Tests Fixes
Date: February 27, 2025

## Issues Identified

After running the goal feature tests in `backend_tests/features/test_goals/test_goal_features.py`, several critical issues were discovered:

1. **Missing Required Constraint Fields**:
   - Error: `GoalConstraintError: Missing required constraint fields: conditions, brands, max_price, min_price`
   - The goal validation requires specific constraint fields that were missing in test data.
   - File: `backend/core/models/goal.py` enforces these constraints in the `validate_goal` function.

2. **Redis Connection Error**:
   - Error: `socket.gaierror: [Errno 11001] getaddrinfo failed` when trying to connect to "redis:6379"
   - The test is attempting to connect to a Redis server that doesn't exist in the test environment.
   - This cascades into `APIServiceUnavailableError` when trying to invalidate goal cache.

3. **Deadline Validation Error**:
   - Error: `GoalValidationError: Deadline must be in the future`
   - Test is creating goals with past deadlines, which violates the model validation.

4. **Insufficient Token Balance**:
   - Error: `TokenTransactionError: Token transaction error service_fee during deduct_service_fee: Failed to deduct service fee: Insufficient balance for deduction`
   - The test is attempting to deduct tokens but the user has insufficient balance.

5. **Negative Price Validation**:
   - Error: `GoalConstraintError: Minimum price must be a non-negative number`
   - Test is creating goals with price ranges that include negative values.

## Planned Fixes

### 1. Fix GoalFactory Constraints

Update the `initialize_constraints` method in `GoalFactory` to ensure all required fields are present:

```python
@post_generation
def initialize_constraints(self, create: bool, extracted: dict, **kwargs):
    """Initialize constraints to ensure all required fields are present."""
    # Ensure constraints is a dictionary, not None
    if not hasattr(self, 'constraints') or not self.constraints:
        self.constraints = {}
    
    # Required fields with default values if missing
    required_fields = {
        'min_price': 100.0,
        'max_price': 500.0,
        'brands': ['samsung', 'apple', 'sony'],
        'conditions': ['new', 'like_new', 'good'],
        'keywords': ['electronics', 'gadget', 'tech']
    }
    
    # Add any missing required fields
    for field, default_value in required_fields.items():
        if field not in self.constraints:
            self.constraints[field] = default_value
    
    # Handle price_range if present
    if 'price_range' in self.constraints:
        price_range = self.constraints['price_range']
        if isinstance(price_range, dict):
            if 'min' in price_range:
                self.constraints['min_price'] = float(price_range['min'])
            if 'max' in price_range:
                self.constraints['max_price'] = float(price_range['max'])
```

### 2. Mock Redis for Feature Tests

Enhance the Redis mock implementation in `conftest.py` to ensure it's consistently used:

```python
@pytest.fixture(scope="function", autouse=True)
async def mock_redis_for_features():
    """Mock Redis for all feature tests."""
    # Patch get_redis_service to return our mock
    with patch('core.services.redis.get_redis_service', return_value=redis_mock):
        # Reset the mock Redis state
        await redis_mock.flushdb()
        
        logger.info("Redis mock initialized for feature test")
        yield
        
        # Cleanup
        await redis_mock.flushdb()
        logger.info("Redis mock cleaned up after feature test")
```

### 3. Fix Timezone-aware Deadlines

Ensure all deadlines in tests are in the future and timezone-aware:

```python
# Example fix in test_goal_deadline_workflow
goal = await GoalFactory.create_async(
    db_session=db_session,
    deadline=datetime.now(timezone.utc) + timedelta(days=30),  # Future date with timezone
    user=user
)
```

### 4. Mock Token Balance for Tests

Update the token service to allow tests to succeed without actual balance:

```python
async def mock_deduct_service_fee(user_id, amount, service_type, **kwargs):
    """Mock implementation that pretends the deduction succeeded."""
    return {
        "user_id": user_id,
        "amount": amount,
        "service_type": service_type,
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Apply mock in tests
services['token'].deduct_service_fee = mock_deduct_service_fee
```

### 5. Ensure Non-negative Price Values

Modify the test scenario to use valid price ranges:

```python
goal = await GoalFactory.create_async(
    db_session=db_session,
    constraints={
        'min_price': 80.0,  # Positive value
        'max_price': 120.0,  # Greater than min_price
        'brands': ['TestBrand'],
        'conditions': ['new'],
        'keywords': ['test', 'product']
    },
    user=user
)
```

## Implementation Plan

1. Update `GoalFactory` to ensure all required constraints are present
2. Enhance Redis mocking in `conftest.py` 
3. Fix timezone-aware deadlines in test cases
4. Implement token service mocking for tests
5. Correct price range values in test scenarios

These changes will address the validation and environmental issues causing the test failures, allowing the feature tests to run successfully without modifying the core validation logic. 