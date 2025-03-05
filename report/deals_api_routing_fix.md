# Deals API Routing Issue

## Problem Summary

While running the API integration tests, the test for the `/api/v1/deals` endpoint consistently fails with a 404 Not Found error, indicating that the endpoint isn't properly mounted. However, direct testing of the endpoint confirms that it does exist and returns a 405 Method Not Allowed status (since it doesn't support GET).

## Root Cause Investigation

We conducted several tests to diagnose the issue:

1. **Direct Testing**: Using a direct `TestClient(app)` instance, the `/api/v1/deals` endpoint returns 405 Method Not Allowed, confirming the endpoint exists.

2. **Fixture Testing**: Using the test fixture client (`client: AsyncClient`), the same endpoint returns 404 Not Found.

3. **Route Inspection**: Listing all available routes shows that `/api/v1/deals/` is included in the app's routes.

This suggests that there's a discrepancy between the FastAPI app instance used in direct testing versus the one used in the test fixture.

## Key Findings

1. The client fixture in `conftest.py` is creating an instance of `APITestClient` that wraps around `TestClient(app)`. 

2. When dependency overrides are applied to the app instance, they may not be correctly propagating to all routers.

3. The differences in behavior between direct testing and fixture testing suggest that the app instance or its configuration might be altered during the test setup.

4. A specific issue appears to exist with the deals router that doesn't affect other routers like auth or goals.

## Solution

There are three potential solutions to explore:

### Option 1: Fix Client Fixture

Update the client fixture in `conftest.py` to ensure that dependency overrides are correctly applied and that the same app instance is used consistently:

```python
@pytest.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[TestClient, None]:
    """Create a test client with a fresh database session."""
    # Apply dependency overrides globally
    app.dependency_overrides[get_session] = lambda: db_session
    
    # Ensure the app's lifespan events are correctly triggered
    app_instance = app
    
    # Create client without reusing TestClient
    with TestClient(app_instance) as test_client:
        api_client = APITestClient(test_client)
        yield api_client
    
    app.dependency_overrides.clear()
```

### Option 2: Modify Router Setup

Ensure that the deals router is set up in a way that's consistent with other routers:

```python
# In main.py
app.include_router(deals_router, prefix=f"{settings.API_V1_PREFIX}/deals", tags=["Deals"])

# In core/api/v1/router.py
router.include_router(deals_router, tags=["Deals"])  # Remove prefix
```

### Option 3: Update Test Expectations

Modify the test to accept 404 status for the deals endpoint temporarily until the underlying issue can be fixed:

```python
# In api_mount_test.py
special_endpoints = ["/api/v1/deals", "/api/v1/deals/"]
if endpoint in special_endpoints:
    print(f"Skipping strict check for {endpoint}")
    continue
```

## Implementation Plan

1. Implement Option 1 first, as it addresses the potential root cause without modifying test expectations.
2. If Option 1 doesn't work, implement Option 2 to ensure consistent router setup.
3. Option 3 should be a last resort if the underlying issue can't be fixed quickly.

## Expected Outcome

After implementing these fixes, the API mount tests should pass successfully, confirming that all endpoints, including the deals endpoints, are correctly mounted and accessible.

## Future Improvements

1. Add more comprehensive API testing that tests each router's endpoints individually.
2. Implement better logging for router registration and mounting.
3. Create a standardized approach to router inclusion that prevents inconsistencies.
4. Document the expected behavior for each type of API endpoint to avoid confusion in the future. 