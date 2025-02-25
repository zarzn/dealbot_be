import pytest
from uuid import UUID
from datetime import datetime, timedelta
import time_machine
from core.services.auth import AuthService
from core.services.redis import RedisService
from core.models.user import User
from core.exceptions import AuthenticationError, TokenError, InvalidCredentialsError
from backend_tests.factories.user import UserFactory
from backend_tests.utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def auth_service(db_session):
    """Create auth service instance for tests."""
    redis_service = RedisService()
    await redis_service.init()
    return AuthService(db_session, redis_service)

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_access_token(db_session, auth_service):
    """Test creating an access token."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create access token
    token = await auth_service.create_access_token(user)
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verify token
    payload = await auth_service.verify_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_refresh_token(db_session, auth_service):
    """Test creating a refresh token."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create refresh token
    token = await auth_service.create_refresh_token(user)
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verify token
    payload = await auth_service.verify_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "refresh"

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_verify_invalid_token(auth_service):
    """Test verifying an invalid token."""
    # Test with invalid token format
    with pytest.raises(TokenError):
        await auth_service.verify_token("invalid_token")
    
    # Test with expired token
    expired_token = await auth_service.create_token(
        {"sub": "test", "type": "access"},
        expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(TokenError):
        await auth_service.verify_token(expired_token)

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_blacklist_token(db_session, auth_service):
    """Test blacklisting a token."""
    # Freeze time to prevent token expiration during test
    with time_machine.travel("2023-01-01 12:00:00"):
        user = await UserFactory.create_async(db_session=db_session)
        token = await auth_service.create_access_token(user)
        
        # Blacklist token with skip_expiration_check for testing
        await auth_service.blacklist_token(token, skip_expiration_check=True)
        
        # Verify blacklisted token cannot be used
        with pytest.raises(TokenError):
            await auth_service.verify_token(token, skip_expiration_check=True)

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authenticate_user(db_session, auth_service):
    """Test user authentication."""
    # Create a user with a specific password that can be verified consistently
    password = "test_password123"
    
    # Add a debug output to understand what's happening
    import sys
    print("Creating test user with password:", password, file=sys.stderr)
    
    user = await UserFactory.create_async(
        db_session=db_session,
        password=password
    )
    await db_session.commit()
    
    # Test valid credentials - try to authenticate with the same password
    try:
        authenticated_user = await auth_service.authenticate_user(
            user.email,
            password
        )
        assert authenticated_user.id == user.id
        print("Authentication successful", file=sys.stderr)
    except Exception as e:
        print(f"Authentication error: {str(e)}", file=sys.stderr)
        raise
    
    # Test invalid password
    with pytest.raises((AuthenticationError, InvalidCredentialsError)):
        await auth_service.authenticate_user(
            user.email,
            "wrong_password"
        )
    
    # Test non-existent user
    with pytest.raises((AuthenticationError, InvalidCredentialsError)):
        await auth_service.authenticate_user(
            "nonexistent@example.com",
            password
        ) 