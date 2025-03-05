# Token Service Test Fixes

## Issue Description

Token service tests were failing due to missing required parameters in token exception constructors. This issue was identified by linter errors showing up in the `backend/core/services/token.py` file.

## Specific Issues

The following token exception constructor calls were missing required parameters:

1. `TokenTransactionError` was missing the `details` parameter in the `rollback_transaction` method.
2. `TokenPricingError` was missing in the imports and not being used in the `get_pricing_info` method.

## Investigation

Examining the token exception classes in `backend/core/exceptions/token_exceptions.py` revealed that:

1. `TokenTransactionError` requires the following parameters:
   - `transaction_id`: A string identifier for the transaction
   - `operation`: The operation that was being performed
   - `reason`: The reason for the error
   - `details`: A dictionary with additional error details

2. `TokenPricingError` requires:
   - `operation`: The operation being performed
   - `reason`: The reason for the error
   - `details`: Optional additional details

Without these required parameters, the exception constructors would fail, causing the tests to fail.

## Implemented Fixes

### 1. Fixed Rollback Transaction Method

Added the missing `details` parameter to the `TokenTransactionError` constructor in the `rollback_transaction` method:

```python
async def rollback_transaction(self, tx_id: str) -> bool:
    """Rollback a failed transaction"""
    try:
        result = await self.repository.rollback_transaction(tx_id)
        logger.info(f"Successfully rolled back transaction {tx_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to rollback transaction {tx_id}: {str(e)}")
        raise TokenTransactionError(
            transaction_id=tx_id,
            operation="rollback_transaction",
            reason=f"Failed to rollback transaction: {str(e)}",
            details={"transaction_id": tx_id}  # Added missing details parameter
        )
```

### 2. Fixed Get Pricing Info Method

Imported the `TokenPricingError` class and used it properly in the `get_pricing_info` method instead of re-raising the original exception:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_pricing_info(self, service_type: str) -> Optional[TokenPricing]:
    """Get token pricing for specific service type"""
    try:
        pricing = await self.repository.get_pricing_by_service(service_type)
        logger.debug(f"Retrieved pricing info for service {service_type}")
        return pricing
    except Exception as e:
        logger.error(f"Failed to get pricing info for service {service_type}: {str(e)}")
        raise TokenPricingError(
            operation="get_pricing_info",
            reason=f"Failed to get pricing info: {str(e)}",
            details={"service_type": service_type}
        )
```

## Verification

After implementing these fixes, all token service tests are now passing:

```
backend_tests/services/test_token_service.py::test_get_balance PASSED
backend_tests/services/test_token_service.py::test_transfer_tokens PASSED
backend_tests/services/test_token_service.py::test_insufficient_balance PASSED
backend_tests/services/test_token_service.py::test_service_fee PASSED
backend_tests/services/test_token_service.py::test_transaction_history PASSED
backend_tests/services/test_token_service.py::test_balance_cache PASSED
backend_tests/services/test_token_service.py::test_transaction_validation PASSED
backend_tests/services/test_token_service.py::test_token_transaction_creation PASSED
backend_tests/services/test_token_service.py::test_token_balance_calculation PASSED
backend_tests/services/test_token_service.py::test_token_transaction_validation PASSED
```

All 10 token service tests now pass successfully.

## Lessons Learned

1. Always make sure to provide all required parameters when raising custom exceptions
2. Check the exception class constructors to understand their parameter requirements
3. For custom exceptions, provide detailed error information to help with debugging
4. Use appropriate exception types for different error scenarios
5. Include contextual information in exception details 

## Going Forward

To prevent similar issues in the future:

1. Consider adding type hints and docstrings to make exception parameters more clear
2. Implement linting checks to catch missing required parameters early
3. Create helper functions for constructing common exceptions with required parameters
4. Update test cases to verify that exceptions are raised with the correct parameters
5. Document exception handling patterns in the project wiki or documentation 