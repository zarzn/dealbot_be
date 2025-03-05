# Auth Integration Tests Issues and Solutions

## Issues Identified

While running the integration tests, the following issues were observed:

1. **Redis Mock Issues**: Errors in Redis operations were occurring, with messages like:
   ```
   Error getting Redis key blacklist:[token]: '_AsyncHiredisParser' object has no attribute '_connected'
   ```
   and
   ```
   'str' object cannot be interpreted as an integer
   ```

2. **Token Verification Failures**: JWT token verification issues:
   ```
   Error verifying token: Signature has expired.
   ```

3. **Test Client Method Usage**: Some tests were possibly using `client.post()` instead of `client.apost()` for asynchronous operations.

## Root Causes

1. **Redis Mock Implementation**: The Redis mock used in testing is incomplete or incorrectly configured:
   - Missing methods or attributes needed for token blacklisting
   - Type conversion issues with keys or values
   - Connection management issues in the async context

2. **JWT Testing Configuration**: The test environment may have incorrect JWT settings:
   - Expired tokens being used in tests
   - Wrong secret keys
   - Missing warning suppressions for expected verification failures

3. **Inconsistent Async Method Usage**: Some test methods are using synchronous client methods in an async context, which can lead to unexpected behaviors.

## Solutions

### 1. Enhance Redis Mock Implementation

Improve the Redis mock to properly handle token blacklisting:

```python
class RedisMock:
    def __init__(self):
        self.data = {}
        self._connected = True  # Add this attribute
    
    async def get(self, key):
        # Ensure proper type handling
        string_key = str(key) if not isinstance(key, str) else key
        return self.data.get(string_key)
    
    async def set(self, key, value, **kwargs):
        # Ensure proper type handling
        string_key = str(key) if not isinstance(key, str) else key
        self.data[string_key] = value
        return True
        
    # Add other necessary methods
```

### 2. Update Auth Service Test Configuration

Modify the auth service test configuration to handle token expiration:

```python
# In test setup
@pytest.fixture
def auth_test_settings():
    # Override settings for testing
    old_jwt_secret = settings.JWT_SECRET_KEY
    old_expiration = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    # Set longer expiration for tests
    settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60
    settings.JWT_SECRET_KEY = "test_secret_key"
    
    yield
    
    # Restore original settings
    settings.JWT_SECRET_KEY = old_jwt_secret
    settings.ACCESS_TOKEN_EXPIRE_MINUTES = old_expiration
```

### 3. Standardize Test Client Usage

Ensure all tests use the proper async methods:

```python
# Instead of
response = client.post("/api/v1/auth/login", ...)

# Use
response = await client.apost("/api/v1/auth/login", ...)
```

## Implementation Recommendations

1. Update the Redis mock in `backend/backend_tests/utils/redis_mock.py`
2. Add JWT test configuration in `backend/backend_tests/conftest.py`
3. Review all auth tests to ensure they use async client methods consistently
4. Add better error logging in the Redis service to make debugging easier

## Expected Outcomes

After implementing these changes, the auth integration tests should run successfully with:

- Proper Redis mock functionality for token operations
- Consistent JWT token verification behavior
- Correct async client usage throughout tests

This will establish a more reliable testing environment for all API tests that involve authentication. 