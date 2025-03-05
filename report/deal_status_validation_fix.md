# Deal Status Validation Fix

## Issue
Tests were failing when an invalid status was assigned to a Deal model. Specifically, the `test_deal_status_transitions` test was failing with an error:

```
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.InvalidTextRepresentationError'>: неверное значение для перечисления dealstatus: "invalid_status"
```

The test expected a ValueError to be raised when an invalid status was assigned, but instead the error was only caught at the database level during the commit operation.

## Root Cause
The Deal model was missing validation for the `status` field in its `__setattr__` method. Unlike other fields (title, url, price, source), there was no validation to ensure that the status value was one of the valid `DealStatus` enum values before it was assigned to the instance.

## Fix
Added validation for the `status` field in the `__setattr__` method of the Deal model, which now:
1. Checks if the value is already a valid `DealStatus` enum instance
2. If it's a string, validates it against the list of valid enum values
3. Raises a ValueError with a descriptive message if the value is invalid

```python
elif key == "status" and value is not None:
    # Validate status values
    if isinstance(value, DealStatus):
        # Value is already a valid enum
        pass
    elif isinstance(value, str):
        # Check if the string is a valid enum value
        valid_values = [status.value for status in DealStatus]
        if value not in valid_values:
            raise ValueError(f"Invalid status: {value}. Valid values are {valid_values}")
```

## Impact
The fix ensures that:
1. Invalid status values are caught early, at the time of assignment rather than at commit time
2. The error message is more descriptive, showing which values are valid
3. The test case now passes correctly, with the validation error happening at the Python level rather than at the database level

This validation follows the same pattern established for other fields in the Deal model and makes the error handling more consistent across the codebase. 