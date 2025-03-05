# Service Test Fixes

## Fix 1: Service Constructor Arguments
**Date**: 2024-02-25
**Test Files**: Multiple service test files
**Issue**: Service constructors were being called with too many arguments

### Problem Details
Services were being initialized with both `db_session` and `redis_service` as positional arguments, but the constructors were defined to take only one argument:

```python
# In service files:
def __init__(self, db_session):
    self.db = db_session

# In test files:
service = ServiceClass(db_session, redis_service)  # Error: too many arguments
```

### Fix Applied
1. Updated service constructors to accept both arguments:
```python
def __init__(self, db_session, redis_service=None):
    self.db = db_session
    self._redis = redis_service
```

### Validation
- Ensured all service classes follow the same pattern
- Updated test fixtures to pass both arguments correctly
- Ran tests to confirm fix

### Important Notes
- Service classes should have consistent constructor patterns
- Consider using dependency injection for Redis service
- Document required constructor arguments

### Related Files
- All service class files under `backend/core/services/`
- All service test files under `backend_tests/services/`

## Fix 2: CacheError Constructor
**Date**: 2024-02-25
**Test Files**: `backend_tests/services/test_cache_service.py`
**Issue**: CacheError exception was missing required arguments

### Problem Details
The CacheError exception requires `cache_key` and `operation` arguments, but they weren't being provided:

```python
# Current code:
raise CacheError(f"Cache set operation failed: {str(e)}")

# Error:
TypeError: CacheError.__init__() missing 2 required positional arguments: 'cache_key' and 'operation'
```

### Fix Applied
1. Updated error raising to include required arguments:
```python
raise CacheError(
    message=f"Cache operation failed: {str(e)}",
    cache_key=key,
    operation=operation
)
```

### Validation
- Updated all CacheError raises to include required arguments
- Ensured error messages are descriptive
- Ran tests to confirm fix

### Important Notes
- Custom exceptions should have clear documentation
- Consider making some constructor arguments optional
- Maintain consistent error handling patterns

### Related Files
- `backend/core/services/cache.py`
- `backend/core/exceptions/__init__.py`
- `backend_tests/services/test_cache_service.py`

## Fix 3: Redis Connection
**Date**: 2024-02-25
**Test Files**: Multiple test files
**Issue**: Tests failing to connect to Redis at "deals_redis:6379"

### Problem Details
Tests are trying to connect to Redis using a Docker service name, but tests are running outside Docker:

```
Error 11001 connecting to deals_redis:6379. getaddrinfo failed
```

### Fix Applied
1. Updated Redis connection configuration for tests:
```python
# In test configuration
TEST_REDIS_URL = "redis://localhost:6379/1"  # Use localhost for tests
```

### Validation
- Updated Redis configuration in test setup
- Added Redis service check in test fixtures
- Ran tests to confirm fix

### Important Notes
- Test environment should use localhost Redis
- Consider adding Redis health check
- Document Redis setup requirements

### Related Files
- `backend/core/config.py`
- `backend_tests/conftest.py`
- `backend/core/services/redis.py`

## Fix 4: AuthService TokenError Initialization
**Date**: 2024-02-25
**Test Files**: `backend_tests/services/test_auth_service.py`
**Issue**: Missing required 'token_type' argument in TokenError initialization

### Problem Details
The `TokenError` exception from auth_exceptions.py requires 'token_type', 'error_type', and 'reason' parameters, but was being initialized with just a message:

```python
except jwt.JWTError as e:
    logger.error(f"Error blacklisting token: {str(e)}")
    raise TokenError(f"Token error: {str(e)}")  # Missing required arguments
```

### Fix Applied
1. Updated TokenError initialization to include all required parameters:
```python
except jwt.JWTError as e:
    logger.error(f"Error blacklisting token: {str(e)}")
    raise TokenError(
        token_type="access",
        error_type="invalid",
        reason=f"Token error: {str(e)}"
    )
```

### Validation
- Updated all TokenError raises in auth.py to include required arguments
- Ensured error messages are descriptive
- Ran tests to confirm fix

### Important Notes
- There are two different TokenError classes in the codebase which can cause confusion
- Consider consolidating exception classes to avoid duplication
- Maintain consistent error handling patterns

### Related Files
- `backend/core/services/auth.py`
- `backend/core/exceptions/auth_exceptions.py`
- `backend/core/exceptions/token_exceptions.py`

## Fix 5: MarketService Method Compatibility
**Date**: 2024-02-25
**Test Files**: `backend_tests/services/test_market_service.py`
**Issue**: Method signature mismatch between tests and implementation

### Problem Details
The test was passing keyword arguments to create_market(), but the method was expecting a MarketCreate object:

```python
# In test:
market = await market_service.create_market(name="Test Market", type=MarketType.TEST.value, ...)

# In implementation:
async def create_market(self, market_data: MarketCreate) -> Market:
    # ...
```

Additionally, the get_market() method was raising NotFoundException instead of the expected MarketNotFoundError.

### Fix Applied
1. Updated create_market method to accept keyword arguments:
```python
async def create_market(self, **kwargs) -> Market:
    try:
        # Check if market with same type already exists
        market_type = kwargs.get('type')
        if market_type:
            existing_market = await self.market_repository.get_by_type(market_type)
            if existing_market:
                raise ValidationError(f"Market with type {market_type} already exists")

        # Create the market directly using kwargs
        return await self.market_repository.create(kwargs)
    except Exception as e:
        raise ValidationError(f"Failed to create market: {str(e)}")
```

2. Updated get_market to raise the correct exception type:
```python
async def get_market(self, market_id: UUID) -> Market:
    try:
        market = await self.market_repository.get_by_id(market_id)
        if not market:
            raise MarketNotFoundError(f"Market with id {market_id} not found")
        return market
    except MarketNotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(
            operation="get_market",
            detail=f"Failed to get market: {str(e)}"
        )
```

### Validation
- Updated method signatures to match test expectations
- Ensured error handling is consistent
- Ran tests to confirm fix

### Important Notes
- Service methods should have flexible parameter handling
- Exception types should be consistent throughout the application
- Consider adding parameter validation to prevent unexpected inputs

### Related Files
- `backend/core/services/market.py`
- `backend/core/exceptions/market_exceptions.py`

## Fix 6: TokenService Missing Methods
**Date**: 2024-02-25
**Test Files**: `backend_tests/services/test_token_service.py`
**Issue**: Missing required methods in TokenService implementation

### Problem Details
The SolanaTokenService class was missing several methods required by the tests:

```
AttributeError: 'SolanaTokenService' object has no attribute 'get_balance'
AttributeError: 'SolanaTokenService' object has no attribute 'transfer'
```

### Fix Applied
1. Added missing methods to SolanaTokenService:
   - get_balance
   - transfer
   - deduct_service_fee
   - clear_balance_cache
   - validate_transaction

Example implementation:
```python
async def get_balance(self, user_id: str) -> Decimal:
    """Get user's token balance."""
    try:
        # Try to get from cache first if redis is available
        if self._redis:
            cached_balance = await self._redis.get(f"balance:{user_id}")
            if cached_balance:
                balance = Decimal(cached_balance.decode())
                return balance
        
        # Get from repository
        balance = await self.repository.get_user_balance(user_id)
        
        # Cache the result if redis is available
        if self._redis:
            await self._redis.setex(
                f"balance:{user_id}",
                settings.BALANCE_CACHE_TTL,
                str(balance)
            )
        
        return balance
    except Exception as e:
        raise TokenBalanceError(
            operation="get_balance",
            reason=f"Failed to get balance: {str(e)}",
            balance=None
        )
```

### Validation
- Implemented all missing methods according to the test requirements
- Added caching logic for performance improvement
- Ensured proper error handling

### Important Notes
- Service interfaces should be clearly defined
- Consider using abstract base classes to enforce interface contracts
- Add comprehensive docstrings to all methods

### Related Files
- `backend/core/services/token.py`
- `backend/core/repositories/token.py` 