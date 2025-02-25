import pytest
from httpx import AsyncClient
from factories.user import UserFactory
from utils.markers import integration_test, depends_on

pytestmark = pytest.mark.asyncio

@integration_test
@depends_on("services.test_user.test_auth_service.test_authenticate_user")
async def test_login_endpoint(client):
    """Test the login endpoint."""
    # Create a test user
    password = "TestPassword123!"
    user = await UserFactory.create_async(
        email="test@example.com",
        password=password
    )
    
    # Test successful login
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": password
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Test invalid credentials
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!"
        }
    )
    
    assert response.status_code == 401

@integration_test
@depends_on("services.test_user.test_auth_service.test_token_operations")
async def test_protected_endpoint(client):
    """Test accessing a protected endpoint."""
    # Create a test user and get token
    user = await UserFactory.create_async()
    response = await client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "password": UserFactory.get_test_password()
        }
    )
    
    token = response.json()["access_token"]
    
    # Test accessing protected endpoint
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user.email
    
    # Test accessing without token
    response = await client.get("/api/users/me")
    assert response.status_code == 401
    
    # Test with invalid token
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

@integration_test
@depends_on("services.test_user.test_auth_service.test_token_operations")
async def test_logout_endpoint(client):
    """Test the logout endpoint."""
    # Create a test user and get token
    user = await UserFactory.create_async()
    response = await client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "password": UserFactory.get_test_password()
        }
    )
    
    token = response.json()["access_token"]
    
    # Test logout
    response = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    # Verify token is blacklisted
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401