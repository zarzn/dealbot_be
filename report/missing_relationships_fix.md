# Missing Relationships Fix

## Issue Summary

Several test failures were occurring due to SQLAlchemy mapper initialization errors. The specific error was:

```
sqlalchemy.exc.InvalidRequestError: One or more mappers failed to initialize - can't proceed with initialization of other mappers. Triggering mapper: 'Mapper[PriceTracker(price_trackers)]'. Original exception was: Mapper 'Mapper[Deal(deals)]' has no property 'price_trackers'. If this property was indicated from other mappers or configure events, ensure registry.configure() has been called.
```

The errors were occurring because the `price_trackers` relationship was defined in the `relationships.py` file but not in the actual model class definitions.

## Changes Made

1. Added missing `price_trackers` relationship to the `Deal` model in `backend/core/models/deal.py`:
   ```python
   price_trackers = relationship("PriceTracker", back_populates="deal", cascade="all, delete-orphan")
   ```

2. Added missing `price_trackers` relationship to the `User` model in `backend/core/models/user.py`:
   ```python
   price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")
   ```

3. Ensured relationship declarations are consistent between the model files and the `relationships.py` file.

## Root Cause Analysis

The issue occurred because:

1. The `PriceTracker` model in `price_tracking.py` correctly declared its relationships to both the `Deal` and `User` models.
2. The relationship setup in `relationships.py` correctly defined the relationships.
3. However, the `Deal` and `User` models themselves were missing the corresponding relationship declarations.

This created a mismatch between what was defined in the model files and what was being set up in the `relationships.py` file, leading to SQLAlchemy mapper initialization failures.

## Best Practices for Future Development

1. **Consistent Relationship Declarations**: When adding new relationships, ensure they are declared in both:
   - The model class definitions
   - The `relationships.py` setup function

2. **Model Validation**: Regularly test model initialization to catch relationship definition mismatches earlier.

3. **Database Schema Changes**: When making changes to the database schema or model relationships:
   - Update the migration scripts
   - Update all relevant model files
   - Test with a full database reset to ensure consistency

4. **Error Handling**: When troubleshooting relationship errors, check both sides of the relationship for proper configuration.

## Verification

The changes resolve the SQLAlchemy mapper initialization errors, allowing the tests to proceed without failing on model initialization. 