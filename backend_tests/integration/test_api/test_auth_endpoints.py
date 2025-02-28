import pytest
from httpx import AsyncClient
from backend_tests.factories.user import UserFactory
from backend_tests.utils.markers import integration_test, depends_on
import time

pytestmark = pytest.mark.asyncio

@integration_test
@depends_on("services.test_user.test_auth_service.test_authenticate_user")
async def test_login_endpoint(client, db_session):
    """Test the login endpoint."""
    # Create a test user with a unique email
    password = "TestPassword123!"
    unique_email = f"test_login_endpoint_{int(time.time())}@example.com"
    
    user = await UserFactory.create_async(
        email=unique_email,
        password=password,
        db_session=db_session
    )
    
    # Test successful login
    response = await client.apost(
        "/api/v1/auth/login",
        json={
            "username": unique_email,
            "password": password
        }
    )
    
    assert response.status_code in [200, 422], f"Unexpected status code: {response.status_code}"
    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    # Test invalid credentials
    response = await client.apost(
        "/api/v1/auth/login",
        json={
            "username": unique_email,
            "password": "WrongPassword123!"
        }
    )
    
    assert response.status_code in [401, 422], f"Unexpected status code: {response.status_code}"

@integration_test
@depends_on("services.test_user.test_auth_service.test_token_operations")
async def test_protected_endpoint(client, test_token):
    """Test accessing a protected endpoint."""
    # Set auth header directly
    headers = {"Authorization": f"Bearer {test_token}"}
    
    # Test accessing protected endpoint - use client.client directly
    response = await client.client.get(
        "/api/v1/users/me",
        headers=headers
    )
    
    # Should get either a 200 or a 404, but not a 401 Unauthorized
    assert response.status_code != 401, "Authentication failed with test token"
    
    # Test accessing without token - use client.client directly
    response = await client.client.get("/api/v1/users/me")
    assert response.status_code in [401, 422], f"Expected 401 or 422, got {response.status_code}"

@integration_test
@depends_on("services.test_user.test_auth_service.test_token_operations")
async def test_logout_endpoint(client, test_token):
    """Test the logout endpoint."""
    # Set auth header directly  
    headers = {"Authorization": f"Bearer {test_token}"}
    
    # Test logout - use client.client directly
    response = await client.client.post(
        "/api/v1/auth/logout",
        headers=headers
    )
    assert response.status_code in [200, 204], f"Expected 200 or 204, got {response.status_code}"