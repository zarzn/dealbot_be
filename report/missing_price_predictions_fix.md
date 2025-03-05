# Missing PricePrediction Relationships Fix

## Issue Identified

The application was throwing SQLAlchemy mapper initialization errors due to missing relationship definitions:

```
sqlalchemy.exc.InvalidRequestError: One or more mappers failed to initialize - can't proceed with initialization of other mappers. Triggering mapper: 'Mapper[PricePrediction(price_predictions)]'. 
Original exception was: Mapper 'Mapper[Deal(deals)]' has no property 'price_predictions'. If this property was indicated from other mappers or configure events, ensure registry.configure() has been called.
```

Then after fixing the Deal model relationship, we encountered a similar error for the User model:

```
sqlalchemy.exc.InvalidRequestError: One or more mappers failed to initialize - can't proceed with initialization of other mappers. Triggering mapper: 'Mapper[PricePrediction(price_predictions)]'. 
Original exception was: Mapper 'Mapper[User(users)]' has no property 'price_predictions'. If this property was indicated from other mappers or configure events, ensure registry.configure() has been called.
```

These errors indicated that the `PricePrediction` model had relationships with both the `Deal` and `User` models via `deal` and `user` attributes, but the corresponding `price_predictions` relationship was missing in both models.

## Changes Made

1. Added the missing relationship to the `Deal` model in `backend/core/models/deal.py`:

```python
# Existing relationships
price_histories = relationship("PriceHistory", back_populates="deal", cascade="all, delete-orphan")
price_trackers = relationship("PriceTracker", back_populates="deal", cascade="all, delete-orphan")
# Added relationship
price_predictions = relationship("PricePrediction", back_populates="deal", cascade="all, delete-orphan")
```

2. Added the missing relationship to the `User` model in `backend/core/models/user.py`:

```python
# Existing relationships
user_preferences = relationship("UserPreferences", back_populates="user", cascade="all, delete-orphan")
price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")
# Added relationship
price_predictions = relationship("PricePrediction", back_populates="user", cascade="all, delete-orphan")
```

3. The `PricePrediction` model in `backend/core/models/price_prediction.py` already had the corresponding relationship declarations:

```python
# Relationships
deal = relationship("Deal", back_populates="price_predictions")
user = relationship("User", back_populates="price_predictions")
```

## Root Cause Analysis

The issue was caused by an inconsistency between model definitions and their relationships. When bidirectional relationships are defined in SQLAlchemy, both sides of the relationship need to be properly specified with matching `relationship()` calls and `back_populates` attributes.

In this case:
- The `PricePrediction` model had a `deal` relationship pointing to `Deal` and a `user` relationship pointing to `User`
- The `Deal` model was missing the corresponding `price_predictions` relationship pointing back to `PricePrediction`
- The `User` model was missing the corresponding `price_predictions` relationship pointing back to `PricePrediction`

This is a common issue that can occur when adding new models and relationships to an existing application, especially when models are defined in different files. The error occurs because SQLAlchemy checks relationship consistency when the first model is instantiated.

## Verification

After adding the missing relationships, the SQLAlchemy mapper initialization succeeded and the specific test for the task service was able to run properly. The bidirectional relationships now allow for:

1. Querying all price predictions for a deal: `deal.price_predictions`
2. Querying all price predictions for a user: `user.price_predictions`
3. Accessing the related deal from a prediction: `price_prediction.deal`
4. Accessing the related user from a prediction: `price_prediction.user`

## Best Practices for Future Development

1. **Consistency in Relationships**: Always ensure that bidirectional relationships are defined on both sides with matching `back_populates` attributes.

2. **Model Validation**: Consider implementing model validation scripts that check for missing relationship definitions before deployment.

3. **Documentation**: Clearly document the expected relationships between models, especially when they span multiple files.

4. **Careful Review of Model Changes**: When adding or updating models, carefully review all the affected relationships to ensure consistency.

5. **Automated Testing**: Include tests that verify the bidirectional relationships are working correctly.

6. **Relationship Templates**: When adding a new model with multiple relationships, use a checklist or template to ensure all relationship sides are properly defined.

7. **Centralized Relationship Management**: Consider implementing a system like the existing `setup_relationships()` function to manage complex relationships in one place.

By following these best practices, we can avoid similar issues in the future and ensure the database models remain consistent. 