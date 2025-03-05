# Deal Initialization Parameter Fix

## Issue

After implementing URL validation in the `Deal` model, tests in `backend_tests/core/test_models/test_deal.py` were still failing with a new error:

```
TypeError: __init__() got an unexpected keyword argument 'user'
```

The specific tests that failed were:
- `test_create_deal`
- `test_deal_price_validation`
- `test_deal_status_transitions`
- `test_deal_relationships`

## Root Cause

In our refactoring of the `Deal` model's `__init__` method, we changed it to use explicit parameters rather than `**kwargs`. However, the `DealFactory` is passing objects directly, like `user`, `market`, and `goal`, but our refactored `__init__` method was expecting their IDs (`user_id`, `market_id`, `goal_id`) instead.

The factory creates object relationships using:
```python
user = SubFactory(UserFactory)
goal = SubFactory(GoalFactory)
market = SubFactory(MarketFactory)
```

When a `Deal` is created in the factory, it passes these objects directly, not their IDs.

## Fix

We updated the `Deal.__init__` method to handle both object instances and IDs:

```python
def __init__(
    self,
    user=None,
    user_id=None,
    market=None,
    market_id=None,
    title: Optional[str] = None,
    # ... other parameters ...
    goal=None,
    goal_id: Optional[UUID] = None,
    # ... other parameters ...
    **kwargs
):
    # Handle user parameter from factory
    if user is not None and hasattr(user, 'id'):
        user_id = user.id
    if user_id is None:
        raise ValueError("user_id is required")

    # Handle market parameter from factory
    if market is not None and hasattr(market, 'id'):
        market_id = market.id
    if market_id is None:
        raise ValueError("market_id is required")
        
    # Handle goal parameter from factory
    if goal is not None and hasattr(goal, 'id'):
        goal_id = goal.id
        
    # ... rest of initialization ...
```

We also made sure to pass through any remaining `**kwargs` to the parent class constructor to maintain backward compatibility with existing code.

## Impact

This fix allows the `Deal` model to work both in production code (where IDs are typically used) and in test code (where object instances are used). It maintains backward compatibility while providing stronger typing and validation for required fields.

The change also clarifies the relationship between the `Deal` model and its related entities (`User`, `Market`, `Goal`), making the code more maintainable and less prone to errors. 