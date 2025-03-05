"""Tests for the authentication service."""

import pytest
import uuid
from datetime import datetime, timedelta
import time_machine
from core.services.auth import AuthService, authenticate_user
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

# Tests from original test_auth_service.py

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_access_token(db_session, auth_service):
    """Test creating an access token."""
    # Create a test user
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create an access token
    token = await auth_service.create_access_token(user)
    
    # Verify token can be decoded
    decoded = await auth_service.verify_token(token)
    assert decoded["sub"] == str(user.id)
    assert decoded["type"] == "access"

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_refresh_token(db_session, auth_service):
    """Test creating a refresh token."""
    # Create a test user
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create a refresh token
    token = await auth_service.create_refresh_token(user)
    
    # Verify token can be decoded
    decoded = await auth_service.verify_token(token)
    assert decoded["sub"] == str(user.id)
    assert decoded["type"] == "refresh"

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_verify_invalid_token(auth_service):
    """Test verifying an invalid token."""
    # Test with invalid token format
    with pytest.raises(TokenError):
        await auth_service.verify_token("invalid_token")
    
    # Test with expired token
    with time_machine.travel(datetime.utcnow() + timedelta(days=2)):
        # Create a test user
        user_id = str(uuid.uuid4())
        
        # Create an access token (which will be expired in the time-traveled future)
        data = {"sub": user_id}
        token = await auth_service.create_access_token(data)
        
        # Verify token is expired
        with pytest.raises(TokenError):
            await auth_service.verify_token(token)

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_blacklist_token(db_session, auth_service):
    """Test blacklisting a token."""
    # Create a test user
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create an access token
    token = await auth_service.create_access_token(user)
    
    # Verify token is valid
    decoded = await auth_service.verify_token(token)
    assert decoded["sub"] == str(user.id)
    
    # Blacklist the token
    await auth_service.blacklist_token(token)
    
    # Verify token is now invalid
    with pytest.raises(TokenError):
        await auth_service.verify_token(token)

# Tests from test_user/test_auth_service.py

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authenticate_user_with_valid_credentials(db_session):
    """Test user authentication with valid credentials."""
    # Create a unique email for this test
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    
    # Create a test user with known credentials
    user = await UserFactory.create_async(
        db_session=db_session,
        email=unique_email,
        password="testpassword123"
    )
    
    # Authenticate the user
    authenticated_user = await authenticate_user(
        email=unique_email,
        password="testpassword123",
        db=db_session
    )
    
    # Verify the authenticated user
    assert authenticated_user is not None
    assert authenticated_user.id == user.id
    assert authenticated_user.email == unique_email

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authentication_failure(db_session):
    """Test authentication failures with invalid credentials."""
    # Create a unique email for this test
    unique_email = f"test_auth_fail_{uuid.uuid4().hex[:8]}@example.com"
    
    # Create a test user with known credentials
    await UserFactory.create_async(
        db_session=db_session,
        email=unique_email,
        password="testpassword123"
    )
    
    # Test with incorrect password
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(
            email=unique_email,
            password="wrongpassword",
            db=db_session
        )
    
    # Test with non-existent user
    with pytest.raises(AuthenticationError):
        await authenticate_user(
            email="nonexistent@example.com",
            password="testpassword123",
            db=db_session
        )
    
    # Test with inactive user
    inactive_email = f"test_auth_inactive_{uuid.uuid4().hex[:8]}@example.com"
    await UserFactory.create_async(
        db_session=db_session,
        email=inactive_email,
        password="testpassword123",
        status="inactive"
    )
    
    with pytest.raises(AuthenticationError):
        await authenticate_user(
            email=inactive_email,
            password="testpassword123",
            db=db_session
        )

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_token_operations(db_session, redis_client):
    """Test token creation, verification, and blacklisting."""
    # Create auth service
    auth_service = AuthService(db_session)
    
    # Create a test user
    user = await UserFactory.create_async(db_session=db_session)
    user_id = str(user.id)
    
    # Create access and refresh tokens
    access_token = await auth_service.create_access_token(user)
    refresh_token = await auth_service.create_refresh_token(user)
    
    # Verify tokens
    access_decoded = await auth_service.verify_token(access_token)
    refresh_decoded = await auth_service.verify_token(refresh_token)
    
    assert access_decoded["sub"] == user_id
    assert access_decoded["type"] == "access"
    assert refresh_decoded["sub"] == user_id
    assert refresh_decoded["type"] == "refresh"
    
    # Blacklist access token
    await auth_service.blacklist_token(access_token)
    
    # Verify blacklisted token is rejected
    with pytest.raises(TokenError):
        await auth_service.verify_token(access_token)
    
    # Refresh token should still be valid
    refresh_decoded_again = await auth_service.verify_token(refresh_token)
    assert refresh_decoded_again["sub"] == user_id 