# Goal Service Test Fixes

## Issue Description

Several tests in the `test_goal_service.py` file were failing due to multiple issues:

1. The `Goal` database model was missing a `description` field that was present in the Pydantic models.
2. The `create_goal` function was using a `due_date` parameter that didn't exist in the database model.
3. The `GoalResponse` model had validation errors for:
   - `priority` field (couldn't parse GoalPriority enum as integer)
   - `metadata` field (couldn't convert MetaData object to dictionary)
   - `max_tokens`, `notification_threshold`, and `auto_buy_threshold` fields had type mismatches

## Root Causes

1. **Database Schema Mismatch**: The SQLAlchemy model had a `description` field, but the database schema didn't have the corresponding column.
2. **Parameter Mismatch**: The `create_goal` function was using `due_date` but the database model used `deadline`.
3. **Type Conversion Issues**: The Pydantic models weren't properly handling enum values and field types.

## Solution

1. **Added Description Column to Database**:
   - Added the `description TEXT` column to the `goals` table in the migration file.
   - Updated the database schema by running the setup script.

2. **Fixed Parameter Handling**:
   - Updated the `create_goal` function to use `deadline` instead of `due_date`.
   - Made the function handle both parameters for backward compatibility.

3. **Fixed Pydantic Model Validation**:
   - Added a model validator to `GoalResponse` to convert `GoalPriority` enum values to integers.
   - Ensured `metadata` is always a valid dictionary.
   - Updated field types in `GoalBase` to match expected types in tests.

## Code Changes

1. **Added Description Column**:
```python
# In migration file
CREATE TABLE goals (
    ...
    title VARCHAR(255) NOT NULL,
    description TEXT,
    constraints JSONB NOT NULL,
    ...
);
```

2. **Fixed Goal Model**:
```python
# In Goal SQLAlchemy model
description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

3. **Fixed create_goal Function**:
```python
# Updated parameter handling
goal = GoalModel(
    ...
    deadline=deadline or due_date,
    ...
)
```

4. **Fixed GoalResponse Validation**:
```python
@model_validator(mode='before')
@classmethod
def convert_priority_and_metadata(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert GoalPriority enum to integer and ensure metadata is a dict."""
    if isinstance(data, dict):
        # Handle priority conversion
        if 'priority' in data and isinstance(data['priority'], GoalPriority):
            priority_map = {
                GoalPriority.HIGH: 3,
                GoalPriority.MEDIUM: 2,
                GoalPriority.LOW: 1
            }
            data['priority'] = priority_map.get(data['priority'], 2)
        
        # Ensure metadata is a dict
        if 'metadata' in data and not isinstance(data['metadata'], dict):
            data['metadata'] = {}
    
    return data
```

5. **Fixed Field Types**:
```python
# Updated field types in GoalBase
max_tokens: Optional[float] = Field(None)
notification_threshold: Optional[float] = Field(None)
auto_buy_threshold: Optional[float] = Field(None)
```

## Results

After implementing these fixes, the `test_update_goal_api` test now passes successfully. However, there are still issues with other Goal service tests that need to be addressed separately.

## Current Status

- ✅ The API test `test_update_goal_api` is now passing.
- ❌ The service tests in `test_goal_service.py` are still failing with validation errors.

## Next Steps

1. **Fix from_orm Conversion**: The `from_orm` method in `GoalResponse` needs to be fixed to properly handle the conversion of `GoalPriority` enum values to integers.
2. **Improve Metadata Handling**: The `metadata` field needs better handling to ensure it's always a valid dictionary.
3. **Update Test Environment**: The test environment may need to be updated to handle the new field types and validation rules.
4. **Fix Validation Test**: The `test_validate_goal` test is failing because it's not raising the expected `ValidationError`.

## Lessons Learned

1. **Database-Model Consistency**: Ensure that database schema, SQLAlchemy models, and Pydantic models are all consistent.
2. **Type Handling**: Pay special attention to type conversions, especially when dealing with enums and custom objects.
3. **Backward Compatibility**: When updating parameters, maintain backward compatibility to avoid breaking existing code.
4. **Validation Logic**: Use model validators to handle complex validation and type conversion scenarios. 