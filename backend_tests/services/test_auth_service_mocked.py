"""Tests for the authentication service with mocked database."""

import pytest
import uuid
from datetime import datetime, timedelta
import time_machine
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from core.services.auth import AuthService, authenticate_user
from core.models.user import User
from core.models.auth_token import TokenType, TokenErrorType
from core.exceptions import AuthenticationError, TokenError, InvalidCredentialsError
from core.utils.security import get_password_hash

pytestmark = pytest.mark.asyncio

# Mock Redis implementation
class RedisMock:
    """Mock implementation of Redis for testing."""
    
    def __init__(self):
        self.data = {}
        self.blacklisted_tokens = set()
    
    async def get(self, key):
        """Get a value from the mock Redis."""
        return self.data.get(key)
    
    async def set(self, key, value, ex=None):
        """Set a key in the mock Redis."""
        if key.startswith("blacklist:"):
            token = key.replace("blacklist:", "")
            self.blacklisted_tokens.add(token)
        else:
            self.data[key] = value
        return True
    
    async def setex(self, key, ttl, value):
        """Set a key with expiration in the mock Redis."""
        if key.startswith("blacklist:"):
            token = key.replace("blacklist:", "")
            self.blacklisted_tokens.add(token)
        else:
            self.data[key] = value
        return True
    
    async def delete(self, key):
        """Delete a key from the mock Redis."""
        if key in self.data:
            del self.data[key]
        return True
    
    async def exists(self, key):
        """Check if a key exists."""
        if key.startswith("blacklist:"):
            token = key.replace("blacklist:", "")
            return token in self.blacklisted_tokens
        return key in self.data
        
    async def is_token_blacklisted(self, token):
        """Check if a token is blacklisted."""
        return token in self.blacklisted_tokens

# Mock user for testing
class MockUser:
    """Mock user for testing."""
    
    def __init__(self, id=None, email="test@example.com", password=None, status="active"):
        self.id = id or uuid.uuid4()
        self.email = email
        self.password = password or get_password_hash("testpassword123")
        self.status = status
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def copy(self):
        """Return a dictionary representation for token creation."""
        return {"sub": str(self.id), "type": "access"}

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return RedisMock()

@pytest.fixture
def auth_service(mock_db_session, mock_redis):
    """Create an auth service with mocked dependencies."""
    return AuthService(mock_db_session, mock_redis)

@pytest.fixture
def mock_user():
    """Create a mock user."""
    return MockUser()

async def test_create_access_token_mocked(auth_service, mock_user):
    """Test creating an access token with mocked user."""
    # Create access token
    token = await auth_service.create_access_token(mock_user)
    
    # Verify token
    decoded = await auth_service.verify_token(token, skip_expiration_check=True)
    
    # Assertions
    assert decoded["sub"] == str(mock_user.id)
    assert decoded["type"] == "access"

async def test_create_refresh_token_mocked(auth_service, mock_user):
    """Test creating a refresh token with mocked user."""
    # Create refresh token
    token = await auth_service.create_refresh_token(mock_user)
    
    # Verify token
    decoded = await auth_service.verify_token(token, skip_expiration_check=True)
    
    # Assertions
    assert decoded["sub"] == str(mock_user.id)
    assert decoded["type"] == "refresh"

async def test_blacklist_token_mocked(auth_service, mock_user):
    """Test blacklisting a token with mocked dependencies."""
    # Create token
    token = await auth_service.create_access_token(mock_user)
    
    # Verify token is valid
    decoded = await auth_service.verify_token(token, skip_expiration_check=True)
    assert decoded["sub"] == str(mock_user.id)
    
    # Blacklist token
    await auth_service.blacklist_token(token)
    
    # Verify token is now invalid (just check that it raises TokenError)
    with pytest.raises(TokenError):
        await auth_service.verify_token(token, skip_expiration_check=True)

async def test_token_operations_mocked(auth_service, mock_user):
    """Test token creation, verification, and blacklisting with mocked dependencies."""
    # Create tokens
    access_token = await auth_service.create_access_token(mock_user)
    refresh_token = await auth_service.create_refresh_token(mock_user)
    
    # Verify tokens
    access_decoded = await auth_service.verify_token(access_token, skip_expiration_check=True)
    refresh_decoded = await auth_service.verify_token(refresh_token, skip_expiration_check=True)
    
    # Assertions
    assert access_decoded["sub"] == str(mock_user.id)
    assert access_decoded["type"] == "access"
    assert refresh_decoded["sub"] == str(mock_user.id)
    assert refresh_decoded["type"] == "refresh"
    
    # Blacklist access token
    await auth_service.blacklist_token(access_token)
    
    # Verify blacklisted token is rejected (just check that it raises TokenError)
    with pytest.raises(TokenError):
        await auth_service.verify_token(access_token, skip_expiration_check=True)
    
    # Refresh token should still be valid
    refresh_decoded_again = await auth_service.verify_token(refresh_token, skip_expiration_check=True)
    assert refresh_decoded_again["sub"] == str(mock_user.id)

async def test_authenticate_user_mocked():
    """Test authenticate_user function with mocked database."""
    # Create mock user with known password
    password = "testpassword123"
    hashed_password = get_password_hash(password)
    
    mock_user = Mock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "test@example.com"
    mock_user.password = hashed_password
    mock_user.status = "active"
    
    # Mock database session
    mock_db = AsyncMock()
    mock_execute = AsyncMock()
    mock_db.execute.return_value = mock_execute
    mock_execute.scalar_one_or_none.return_value = mock_user
    
    # Test with valid credentials
    authenticated_user = await authenticate_user(
        email=mock_user.email,
        password=password,
        db=mock_db
    )
    
    # Assertions
    assert authenticated_user is mock_user

async def test_verify_invalid_token_mocked(auth_service):
    """Test that invalid tokens raise TokenError."""
    # Test with completely invalid token
    with pytest.raises(TokenError):
        await auth_service.verify_token("invalid_token")
    
    # Test with expired token
    with time_machine.travel(datetime.utcnow() + timedelta(days=2)):
        # Create token that will be expired in the time-traveled future
        user_id = str(uuid.uuid4())
        data = {"sub": user_id}
        token = await auth_service.create_access_token(data)
        
        # Verify token is expired
        with pytest.raises(TokenError):
            await auth_service.verify_token(token) 