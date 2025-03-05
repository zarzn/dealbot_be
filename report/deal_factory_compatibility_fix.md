# Deal Factory Compatibility Fix

## Issue
After fixing the source validation in the `Deal` model, tests in `backend_tests/core/test_models/test_deal.py` were failing with a different error:

```
TypeError: __init__() missing 3 required positional arguments: 'user_id', 'market_id', and 'url'
```

This indicated a mismatch between how the `DealFactory` was creating deals and what parameters the `Deal.__init__` method was expecting.

Failing tests:
- `test_create_deal`
- `test_deal_price_validation`
- `test_deal_status_transitions`
- `test_deal_relationships`

## Root Cause
When refactoring the `Deal` model's `__init__` method to add validation for the `title`, `url`, `price`, and `source` fields, we inadvertently changed the method signature to require `user_id`, `market_id`, and `url` as positional arguments, and removed the ability to pass `user` and `market` objects directly.

However, the `DealFactory` was designed to pass `user` and `market` objects, relying on the model to extract the IDs from these objects:

```python
# From DealFactory
user = SubFactory(UserFactory)
market = SubFactory(MarketFactory)
```

## Fix
Modified the `Deal.__init__` method to handle both objects and IDs, like the original version did:

```python
def __init__(
    self,
    user=None,
    user_id=None,
    market=None,
    market_id=None,
    url: str = None,
    goal=None,
    goal_id: UUID = None,
    # ... other parameters
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
        
    # ... other validation code
```

This approach maintains backward compatibility with the `DealFactory` while still ensuring the required fields have valid values.

## Impact
The fix ensures that the `Deal` model can be instantiated in both direct code and through the `DealFactory` in tests. It keeps our validation improvements for `title`, `url`, `price`, and `source` fields while maintaining compatibility with existing test code that expects to be able to pass `user` and `market` objects directly to the constructor. 