# API Routing Issue and Fix

## Issue Description

The API integration tests are failing with 404 errors because the auth endpoints are not being correctly mounted. The tests are looking for endpoints like `/api/v1/auth/login` but receiving 404 Not Found errors.

## Root Cause Analysis

After examining the code, I identified the following issues:

1. **Double Prefix Problem**: The auth router is defined with a prefix of `/auth` in `backend/core/api/v1/auth/router.py`. However, in `main.py`, it is included with a different prefix pattern than other routers:

   ```python
   # In main.py
   app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}", tags=["Authentication"])
   ```

   While other routers have their component included in the prefix:

   ```python
   app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
   ```

2. **Inconsistent Path Construction**: This leads to a path of `/api/v1` (from main.py) + `/auth` (from auth/router.py) for auth endpoints, while other routers get `/api/v1/component` (from main.py) + component-specific endpoints.

3. **Test Client vs Direct Requests**: The `APITestClient` correctly handles adding the `/api/v1` prefix to URLs, but it's essential to maintain consistency in how paths are formed.

## Solution

The solution is to make the auth router prefix consistent with other routers in the `main.py` file. There are two approaches:

### Option 1: Remove the prefix from auth router

Remove the prefix in the auth router definition:

```python
# In backend/core/api/v1/auth/router.py
router = APIRouter(tags=["auth"])  # Remove prefix="/auth"
```

This would work with the current main.py configuration.

### Option 2: Update the main.py include (Recommended)

Change how the auth router is included in main.py to match the pattern of other routers:

```python
# In main.py
app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
```

This is preferred since it maintains consistency with how other routers are included.

## Implementation

I recommend Option 2 to keep the code consistent. This will ensure that the auth router endpoints are accessible at `/api/v1/auth/*` as expected by the tests.

## Verification

After making this change, the API integration tests should pass as they'll be able to access endpoints at the expected paths:
- `/api/v1/auth/login`
- `/api/v1/auth/register`
- `/api/v1/auth/refresh`
- etc.

The APIs will be correctly mounted and accessible to the test client. 