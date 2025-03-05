# Deal Original Price Constraint Fix

## Date
February 27, 2025

## Issue
Integration tests were failing with the following error:

```
IntegrityError: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.CheckViolationError'>: новая строка в отношении "deals" нарушает ограничение-проверку "ch_original_price_gt_price"
```

The error occurred because the database has a check constraint `ch_original_price_gt_price` which requires that `original_price` must be greater than `price`. In the DealFactory, when creating a deal with a very small price (e.g., 0.01), the original_price was being set to price * 1.2 = 0.012, which was not sufficiently greater than the price when considering the NUMERIC(10,2) type in the database.

## Investigation

1. Examined the Deal model in `backend/core/models/deal.py` which confirmed the check constraint:
   ```python
   CheckConstraint(
       'original_price IS NULL OR original_price > price',
       'ch_original_price_gt_price'
   )
   ```

2. Examined the database schema in `backend/migrations/versions/20240219_000001_initial_schema.py` which showed the same constraint:
   ```sql
   CONSTRAINT ch_original_price_gt_price CHECK (original_price IS NULL OR original_price > price)
   ```

3. Examined the DealFactory in `backend/backend_tests/factories/deal.py` which was calculating the original_price as:
   ```python
   kwargs['original_price'] = price * Decimal('1.2')  # 20% higher than the current price
   ```

4. The issue was that for very small prices (e.g., 0.01), the calculated original_price (0.012) was not being recognized as greater than the price due to rounding issues with the NUMERIC(10,2) type.

## Solution

Updated the DealFactory to ensure that the original_price is at least 0.01 more than the price to avoid rounding issues with small values:

```python
# Make sure the difference between original_price and price is at least 0.01
calculated_price = price * Decimal('1.5')  # 50% higher than the current price
if calculated_price - price < Decimal('0.01'):
    kwargs['original_price'] = price + Decimal('0.01')  # Ensure difference is at least 0.01
else:
    kwargs['original_price'] = calculated_price
```

Also updated the fallback cases to use the same approach:

```python
# If original_price is provided but not greater than price, adjust it
kwargs['original_price'] = price + Decimal('0.01')  # Ensure difference is at least 0.01
```

## Verification

1. Ran the specific test that was failing:
   ```
   python -m pytest backend_tests/core/test_models/test_deal.py::test_deal_price_validation -v
   ```
   Result: PASSED

2. Ran all deal-related tests:
   ```
   python -m pytest backend_tests/core/test_models/test_deal.py -v
   ```
   Result: All 4 tests PASSED

3. Ran all core tests:
   ```
   python -m pytest backend_tests/core/ -v
   ```
   Result: All 16 tests PASSED

## Conclusion

The fix ensures that when creating Deal objects with the DealFactory, the original_price is always sufficiently greater than the price to satisfy the database constraint. This is particularly important for small price values where percentage-based calculations might not create a large enough difference due to rounding. 