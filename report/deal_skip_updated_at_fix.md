# Deal Skip Updated At Fix

## Issue
After fixing the NULL price error in the Deal model, tests in `backend_tests/core/test_models/test_deal.py` were still failing, but with a new error:

```
TypeError: '_skip_updated_at' is an invalid keyword argument for Deal
```

This error occurred during the initialization of Deal instances in the following tests:
- `test_create_deal`
- `test_deal_price_validation`
- `test_deal_status_transitions`
- `test_deal_relationships`

## Root Cause
The root cause was that the `_skip_updated_at` parameter was being defined in the `__init__` method and then passed to `super().__init__()`. However, SQLAlchemy's base model doesn't accept this parameter, resulting in the TypeError.

In the `receive_before_update` event listener, the code was checking for the existence of the `_skip_updated_at` attribute, but it wasn't being set properly due to the parameter not being processed by SQLAlchemy.

## Fix
The fix involved two main changes:

1. Setting the `_skip_updated_at` attribute directly on the instance instead of passing it to `super().__init__()`:
   ```python
   # Set the _skip_updated_at attribute directly instead of passing to super().__init__
   self._skip_updated_at = _skip_updated_at
   
   super().__init__(
       # ... other parameters ...
       # Removed _skip_updated_at from here
       **kw,
   )
   ```

2. Improving the event listener to also check the value of `_skip_updated_at`, not just its existence:
   ```python
   # Only update the timestamp if it hasn't been explicitly set
   if not hasattr(target, '_skip_updated_at') or not target._skip_updated_at:
       target.updated_at = datetime.now(timezone.utc)
   ```

## Impact
This fix ensures that:

1. The `_skip_updated_at` parameter can be used during Deal initialization without causing errors
2. The parameter correctly controls whether the `updated_at` timestamp should be updated during model changes
3. Tests can properly create and manipulate Deal instances with the option to skip the automatic timestamp updates

This is particularly important for testing scenarios where timestamps need to be controlled precisely or where multiple updates to a model should not affect the `updated_at` timestamp. 