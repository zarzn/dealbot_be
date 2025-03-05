# Deal Timedelta Import Fix

## Issue

After fixing the initialization parameters in the `Deal` model, tests in `backend_tests/core/test_models/test_deal.py` were still failing with a new error:

```
NameError: name 'timedelta' is not defined
```

This error occurred specifically in the `Deal.__init__` method when trying to set a default expiration date using:

```python
self.expires_at = datetime.utcnow() + timedelta(days=30)
```

The specific tests that failed were:
- `test_create_deal`
- `test_deal_price_validation`
- `test_deal_status_transitions`
- `test_deal_relationships`

## Root Cause

During the refactoring of the `Deal` model's `__init__` method, we added functionality to set a default expiration date 30 days in the future, but the `timedelta` class was not imported from the `datetime` module.

Python needs explicit imports for all classes and functions being used, and without the import for `timedelta`, the code could not recognize this name when trying to use it.

## Fix

We added the missing import at the top of the file:

```python
from datetime import datetime, timezone, timedelta
```

This simple change ensures that the `timedelta` class is available when used to calculate the expiration date.

## Impact

With this fix, the `Deal` model can now properly set default expiration dates for deals, ensuring that deals have a valid expiration timeframe. This is important for features like deal expiration notifications, filtering active deals, and maintaining the overall data quality in the system. 