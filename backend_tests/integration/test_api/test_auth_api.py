import pytest
from httpx import AsyncClient
from core.models.enums import UserStatus
from core.services.auth import AuthService
from core.services.redis import get_redis_service
from factories.user import UserFactory
from utils.markers import integration_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def auth_service(db_session):
    redis_service = await get_redis_service()
    return AuthService(db_session, redis_service)

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_register_api(client: AsyncClient, db_session):
    """Test user registration API endpoint."""
    # Test successful registration
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
            "name": "Test User"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["status"] == UserStatus.ACTIVE.value
    assert "token" in data
    
    # Test duplicate email
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!",
            "name": "Another User"
        }
    )
    assert response.status_code == 400

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_login_api(client: AsyncClient, db_session):
    """Test login API endpoint."""
    # Create test user
    password = "TestPassword123!"
    user = await UserFactory.create_async(
        db_session=db_session,
        email="test@example.com",
        password=password
    )
    
    # Test successful login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": password
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    
    # Test invalid credentials
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "WrongPassword123!"
        }
    )
    assert response.status_code == 401

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_refresh_token_api(client: AsyncClient, auth_service, db_session):
    """Test token refresh API endpoint."""
    # Create user and get tokens
    user = await UserFactory.create_async(db_session=db_session)
    tokens = await auth_service.create_tokens(user)
    
    # Test successful token refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {tokens.refresh_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    # Test with invalid refresh token
    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_logout_api(client: AsyncClient, auth_service, db_session):
    """Test logout API endpoint."""
    # Create user and get token
    user = await UserFactory.create_async(db_session=db_session)
    tokens = await auth_service.create_tokens(user)
    
    # Test successful logout
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens.access_token}"}
    )
    
    assert response.status_code == 200
    
    # Verify token is blacklisted
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"}
    )
    assert response.status_code == 401

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_password_reset_api(client: AsyncClient, db_session):
    """Test password reset API endpoints."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Request password reset
    response = await client.post(
        "/api/v1/auth/reset-password/request",
        json={"email": user.email}
    )
    assert response.status_code == 200
    
    # Get reset token from response
    data = response.json()
    reset_token = data["reset_token"]
    
    # Reset password
    new_password = "NewPassword123!"
    response = await client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token": reset_token,
            "new_password": new_password
        }
    )
    assert response.status_code == 200
    
    # Try login with new password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": new_password
        }
    )
    assert response.status_code == 200

@integration_test
@depends_on("services.test_auth_service.test_authenticate_user")
async def test_protected_api_access(client: AsyncClient, auth_service, db_session):
    """Test protected API endpoint access."""
    # Create user and get token
    user = await UserFactory.create_async(db_session=db_session)
    tokens = await auth_service.create_tokens(user)
    
    # Test access with valid token
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user.id)
    
    # Test access without token
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    
    # Test access with invalid token
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401 