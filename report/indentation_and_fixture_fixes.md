# Test Indentation and Fixture Fixes

## Issues Identified

1. **Indentation Error in test_deal_service.py**: 
   - Error: `IndentationError: expected an indented block after 'try' statement on line 48`
   - The indentation in the `test_create_deal` function was inconsistent, with a misaligned `deal_data` dictionary.

2. **Missing Redis Fixture in test_auth_service.py**:
   - Error: `fixture 'redis' not found`
   - The test was trying to use a `redis` fixture that didn't exist, when it should have been using the `redis_client` fixture.

## Implemented Fixes

### 1. Fixed Indentation in test_deal_service.py

Fixed the indentation issue in the `test_create_deal` function by ensuring proper alignment:

```python
@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_create_deal(db_session, deal_service):
    """Test deal creation"""
    from unittest.mock import patch
    import sys
    
    # Create user and goal
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Store original method reference
    original_calculate_score = deal_service._calculate_deal_score
    
    # Create an async mock function for _calculate_deal_score
    async def mock_calculate_score(*args, **kwargs):
        return 80.0  # Return a fixed score for testing
    
    # Apply the mock
    deal_service._calculate_deal_score = mock_calculate_score

    try:
        # Create deal data
        deal_data = {
            "title": "Test Deal",
            "description": "Test Description",
            "url": f"https://test.com/deal/create_{time.time()}",
            # ...rest of the dictionary...
        }
        
        # ...rest of the test...
    finally:
        # Restore original method
        deal_service._calculate_deal_score = original_calculate_score
```

The issue was that the `deal_data` dictionary was not properly indented inside the `try` block, which caused a Python syntax error.

### 2. Fixed Redis Fixture in test_auth_service.py

Updated the test_token_operations function to use the correct fixture:

```python
@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_token_operations(db_session, redis_client):  # Changed from 'redis' to 'redis_client'
    """Test token creation and validation."""
    # Create a test user
    user = await UserFactory.create_async(
        db_session=db_session,  # Added db_session parameter
        email="test@example.com"
    )
    
    # ...rest of the test...
```

The test was failing because:
1. It was looking for a nonexistent `redis` fixture
2. The `UserFactory.create_async()` call was missing the required `db_session` parameter

## Root Cause Analysis

1. **Indentation Issue**: 
   - The indentation issue likely arose from manual editing of the test file, possibly with mixed tabs and spaces.
   - Since Python uses indentation for code blocks, this kind of error breaks the syntax.

2. **Fixture Naming**: 
   - The fixture inconsistency suggests that the test was written using a different naming convention than what was implemented.
   - The fixture was named `redis_client` in the test configuration, but the test was looking for `redis`.

## Benefits of the Fix

1. **Consistent Test Execution**: All tests in the service layer now run properly without syntax errors.
2. **Improved Code Quality**: Fixed indentation makes the code more readable and maintainable.
3. **Proper Fixture Usage**: Tests now use the correct fixtures, ensuring proper test isolation and cleanup.

## Prevention Strategies

1. **Code Linting**: Use a linter to automatically catch indentation and other syntax issues.
2. **Consistent Fixture Naming**: Establish and document naming conventions for test fixtures.
3. **Automated Testing**: Run tests frequently during development to catch issues early.
4. **Code Reviews**: Have others review code changes to catch potential issues.

## Conclusion

These fixes demonstrate the importance of proper indentation in Python and consistent fixture naming in tests. By addressing these issues, we've made the test suite more reliable and easier to maintain. 