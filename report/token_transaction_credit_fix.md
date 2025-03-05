# Token Transaction Credit Type Fix

## Issue Description

The system was unable to process 'credit' transaction types in token balance operations because:

1. The `TokenTransactionType` enum in `core/models/enums.py` was missing the `CREDIT` value.
2. The database constraint `ch_balance_change_match` on the `token_balance_history` table wasn't configured to handle 'credit' type transactions.

This was causing errors when trying to insert records into the token_balance_history table with a 'credit' transaction type:

```
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.CheckViolationError'>: новая строка в отношении "token_balance_history" нарушает ограничение-проверку "ch_balance_change_match"
```

## Solution

The fix required changes in two places:

1. First, added the `CREDIT` value to the `TokenTransactionType` enum in `core/models/enums.py`:

```python
class TokenTransactionType(str, Enum):
    """Token transaction type enum."""
    REWARD = "reward"
    DEDUCTION = "deduction"
    REFUND = "refund"
    CREDIT = "credit"  # Added this line
```

2. Updated the check constraint in the database to include 'credit' as an operation type that increases the balance, similar to 'reward' and 'refund':

```sql
CONSTRAINT ch_balance_change_match CHECK (
    (
        change_type = 'deduction' AND 
        balance_after = balance_before - change_amount
    ) OR (
        change_type IN ('reward', 'refund', 'credit') AND  -- Added 'credit' here
        balance_after = balance_before + change_amount
    )
)
```

This change was made in the initial migration file `backend/migrations/versions/20240219_000001_initial_schema.py`.

3. The database was then recreated with the updated schema using the `setup_db.py` script.

## Key Findings

- When extending functionality with new enum values, it's essential to update both:
  - The Python enum definition
  - Any database constraints that validate based on those enum values

- The 'credit' transaction type should behave like 'reward' and 'refund' in terms of balance calculation (adding to the current balance).

- The `update_balance` method in `TokenBalance` already supported the 'credit' operation type, but the database constraint wasn't allowing it.

## Testing

The fix was validated by running the service tests. While multiple issues remain with other services, the specific check constraint violation for 'credit' operation type was resolved.

## Next Steps

Further work is needed to address remaining issues with the TokenService, MarketService, and AuthService implementations. 