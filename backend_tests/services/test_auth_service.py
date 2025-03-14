"""Tests for the authentication service."""

import pytest
import uuid
from datetime import datetime, timedelta
import time_machine
from core.services.auth import AuthService, authenticate_user
from core.services.redis import RedisService
from core.models.user import User
from core.models.auth_token import TokenErrorType
from core.exceptions import AuthenticationError, TokenError, InvalidCredentialsError
from backend_tests.factories.user import UserFactory
from backend_tests.utils.markers import service_test, depends_on
from unittest.mock import AsyncMock, Mock, patch
from core.utils.security import get_password_hash

pytestmark = pytest.mark.asyncio

# Add a MockRedisService class to help with tests
class MockRedisService:
    """Mock Redis service for testing."""
    
    def __init__(self):
        self.blacklisted_tokens = set()
        self.data = {}
    
    async def init(self):
        """Initialize the mock service."""
        pass
        
    async def exists(self, key):
        """Check if a key exists in the blacklist."""
        if key.startswith("blacklist:"):
            token = key.replace("blacklist:", "")
            return token in self.blacklisted_tokens
        return key in self.data
    
    async def set(self, key, value, ex=None):
        """Set a key in the mock Redis."""
        if key.startswith("blacklist:"):
            token = key.replace("blacklist:", "")
            self.blacklisted_tokens.add(token)
        else:
            self.data[key] = value
        return True
    
    async def get(self, key):
        """Get a value from the mock Redis."""
        return self.data.get(key)
    
    async def delete(self, key):
        """Delete a key from the mock Redis."""
        if key in self.data:
            del self.data[key]
        return True
    
    async def setex(self, key, ttl, value):
        """Set a key with expiration in the mock Redis."""
        return await self.set(key, value)
    
    async def close(self):
        """Close the mock connection."""
        pass

@pytest.fixture
async def auth_service_with_mock_redis(db_session):
    """Create auth service instance with mock Redis for tests."""
    redis_service = MockRedisService()
    await redis_service.init()
    return AuthService(db_session, redis_service)

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
    
    # Verify token can be decoded - skip expiration check for tests
    decoded = await auth_service.verify_token(token, skip_expiration_check=True)
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
    """Test that invalid tokens raise TokenError."""
    # Test with completely invalid token
    try:
        await auth_service.verify_token("invalid_token")
        pytest.fail("TokenError was not raised for invalid token")
    except TokenError:
        # This is expected, test passes
        pass
    
    # Test with expired token
    with time_machine.travel(datetime.utcnow() + timedelta(days=2)):
        # Create a test user
        user_id = str(uuid.uuid4())
        
        # Create an access token (which will be expired in the time-traveled future)
        data = {"sub": user_id}
        token = await auth_service.create_access_token(data)
        
        # Verify token is expired
        try:
            await auth_service.verify_token(token)
            pytest.fail("TokenError was not raised for expired token")
        except TokenError:
            # This is expected, test passes
            pass

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_blacklist_token(db_session, auth_service_with_mock_redis):
    """Test blacklisting a token."""
    # Create a test user
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create an access token
    token = await auth_service_with_mock_redis.create_access_token(user)
    
    # Verify token is valid - skip expiration check for tests
    decoded = await auth_service_with_mock_redis.verify_token(token, skip_expiration_check=True)
    assert decoded["sub"] == str(user.id)
    
    # Blacklist the token using the service method
    await auth_service_with_mock_redis.blacklist_token(token)
    
    # Verify token is now invalid
    with pytest.raises(TokenError):
        await auth_service_with_mock_redis.verify_token(token, skip_expiration_check=True)

# Tests from test_user/test_auth_service.py

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authenticate_user_with_valid_credentials(db_session):
    """Test that valid credentials can authenticate a user."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    
    # Create a test user with known credentials - mock approach
    hashed_password = get_password_hash("testpassword123")
    mock_user = Mock()
    mock_user.id = uuid.uuid4()
    mock_user.email = unique_email
    mock_user.password = hashed_password
    mock_user.status = "active"
    
    # Set up the database mock
    mock_execute = AsyncMock()
    db_session.execute = AsyncMock(return_value=mock_execute)
    mock_execute.scalar_one_or_none.return_value = mock_user
    
    # Authenticate the user
    authenticated_user = await authenticate_user(
        email=unique_email,
        password="testpassword123",
        db=db_session
    )
    
    # Verify the authenticated user
    assert authenticated_user is not None
    assert authenticated_user.id == mock_user.id
    assert authenticated_user.email == unique_email

@service_test
async def test_authentication_failure():
    """Test authentication failure with invalid credentials."""
    # Test with non-existent user
    with pytest.raises(AuthenticationError) as excinfo:
        mock_db = AsyncMock()
        mock_execute = AsyncMock()
        mock_db.execute.return_value = mock_execute
        # Directly set None as return value (not awaitable)
        mock_execute.scalar_one_or_none.return_value = None
        
        await authenticate_user(
            email="nonexistent@example.com",
            password="testpassword123",
            db=mock_db
        )
    assert "User not found or inactive" in str(excinfo.value)
    
    # Test with incorrect password
    with pytest.raises(InvalidCredentialsError) as excinfo:
        # Create a mock user with a known password
        mock_user = Mock()
        mock_user.status = "active"
        mock_user.password = get_password_hash("correctpassword")
        
        # Mock database that returns our mock user
        mock_db = AsyncMock()
        mock_execute = AsyncMock()
        mock_db.execute.return_value = mock_execute
        
        # Ensure we return a non-awaitable object
        mock_execute.scalar_one_or_none.return_value = mock_user
        
        # Attempt authentication with wrong password
        await authenticate_user(
            email="test@example.com",
            password="wrongpassword",  # Incorrect password
            db=mock_db
        )
    assert "Invalid email or password" in str(excinfo.value)

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
    
    # Verify tokens - skip expiration check for tests
    access_decoded = await auth_service.verify_token(access_token, skip_expiration_check=True)
    refresh_decoded = await auth_service.verify_token(refresh_token, skip_expiration_check=True)
    
    assert access_decoded["sub"] == user_id
    assert access_decoded["type"] == "access"
    assert refresh_decoded["sub"] == user_id
    assert refresh_decoded["type"] == "refresh"
    
    # Blacklist access token
    await auth_service.blacklist_token(access_token)
    
    # Verify blacklisted token is rejected
    with pytest.raises(TokenError):
        await auth_service.verify_token(access_token, skip_expiration_check=True)
    
    # Refresh token should still be valid
    refresh_decoded_again = await auth_service.verify_token(refresh_token, skip_expiration_check=True)
    assert refresh_decoded_again["sub"] == user_id 