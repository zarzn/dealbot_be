"""Tests for Social Service.

This module contains tests for the social authentication service, which handles
OAuth verification for various social providers.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from aiohttp.client_exceptions import ClientError

from core.services.social import (
    verify_google_token,
    verify_facebook_token,
    verify_social_token,
    SocialUserInfo
)
from core.exceptions import SocialAuthError
from core.config import settings
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_google_response():
    """Create a mock Google OAuth API response."""
    return {
        "sub": "12345678901234567890",
        "email": "test@gmail.com",
        "email_verified": True,
        "name": "Test User",
        "picture": "https://lh3.googleusercontent.com/a/test_image",
        "given_name": "Test",
        "family_name": "User",
        "locale": "en"
    }

@pytest.fixture
def mock_facebook_response():
    """Create a mock Facebook OAuth API response."""
    return {
        "id": "9876543210",
        "email": "test@example.com",
        "name": "Test Facebook User",
        "picture": {
            "data": {
                "url": "https://platform-lookaside.fbsbx.com/platform/profilepic/test_image"
            }
        }
    }

class MockResponse:
    """Mock response class for aiohttp."""
    
    def __init__(self, data, status=200):
        """Initialize the mock response."""
        self.data = data
        self.status = status
        
    async def json(self):
        """Return mock JSON data."""
        return self.data
        
    async def __aenter__(self):
        """Enter async context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        pass

@service_test
async def test_verify_google_token_success(mock_google_response):
    """Test successful verification of Google OAuth token."""
    # Setup
    token = "valid_google_token"
    
    # Mock aiohttp.ClientSession
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value = MockResponse(mock_google_response)
        
        # Execute
        result = await verify_google_token(token)
        
        # Verify
        assert result is not None
        assert isinstance(result, SocialUserInfo)
        assert result.id == mock_google_response["sub"]
        assert result.email == mock_google_response["email"]
        assert result.name == mock_google_response["name"]
        assert result.picture == mock_google_response["picture"]
        assert result.provider == "google"
        
        # Verify correct URL was called
        mock_get.assert_called_once_with(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")

@service_test
async def test_verify_google_token_invalid():
    """Test verification of invalid Google OAuth token."""
    # Setup
    token = "invalid_google_token"
    
    # Mock aiohttp.ClientSession with error response
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value = MockResponse({}, status=401)
        
        # Execute & Verify
        with pytest.raises(SocialAuthError) as excinfo:
            await verify_google_token(token)
        
        # Verify error details
        assert "Invalid Google token" in str(excinfo.value)

@service_test
async def test_verify_google_token_network_error():
    """Test handling of network errors during Google OAuth verification."""
    # Setup
    token = "valid_google_token"
    
    # Mock aiohttp.ClientSession with network error
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ClientError("Network error")
        
        # Execute & Verify
        with pytest.raises(SocialAuthError) as excinfo:
            await verify_google_token(token)
        
        # Verify error details
        assert "Google authentication failed" in str(excinfo.value)

@service_test
async def test_verify_facebook_token_success(mock_facebook_response):
    """Test successful verification of Facebook OAuth token."""
    # Setup
    token = "valid_facebook_token"
    
    # Create a valid token response for the first API call
    token_response = {
        "data": {
            "is_valid": True,
            "app_id": "123456789",
            "user_id": "9876543210"
        }
    }
    
    # Mock aiohttp.ClientSession
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Set up the mock to return different responses for different URLs
        def side_effect(*args, **kwargs):
            url = args[0]
            if "debug_token" in url:
                return MockResponse(token_response)
            else:
                return MockResponse(mock_facebook_response)
        
        mock_get.side_effect = side_effect
        
        # Execute
        result = await verify_facebook_token(token)
        
        # Verify
        assert result is not None
        assert isinstance(result, SocialUserInfo)
        assert result.id == mock_facebook_response["id"]
        assert result.email == mock_facebook_response["email"]
        assert result.name == mock_facebook_response["name"]
        assert result.picture == mock_facebook_response["picture"]["data"]["url"]
        assert result.provider == "facebook"
        
        # Verify both API calls were made
        assert mock_get.call_count == 2
        
        # Verify the correct URLs were called
        mock_get.assert_any_call(
            f"https://graph.facebook.com/debug_token?input_token={token}&access_token={settings.FACEBOOK_APP_TOKEN}"
        )
        mock_get.assert_any_call(
            f"https://graph.facebook.com/me?fields=id,email,name,picture&access_token={token}"
        )

@service_test
async def test_verify_facebook_token_invalid():
    """Test verification of invalid Facebook OAuth token."""
    # Setup
    token = "invalid_facebook_token"
    
    # Mock aiohttp.ClientSession with error response
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value = MockResponse(
            {"error": {"message": "Invalid OAuth access token", "code": 190}},
            status=401
        )
        
        # Execute & Verify
        with pytest.raises(SocialAuthError) as excinfo:
            await verify_facebook_token(token)
        
        # Verify error details
        assert "Invalid Facebook token" in str(excinfo.value)

@service_test
async def test_verify_facebook_token_network_error():
    """Test handling of network errors during Facebook OAuth verification."""
    # Setup
    token = "valid_facebook_token"
    
    # Mock aiohttp.ClientSession with network error
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ClientError("Network error")
        
        # Execute & Verify
        with pytest.raises(SocialAuthError) as excinfo:
            await verify_facebook_token(token)
        
        # Verify error details
        assert "Facebook authentication failed" in str(excinfo.value)

@service_test
async def test_verify_facebook_token_missing_email():
    """Test Facebook OAuth verification when email is missing."""
    # Setup
    token = "valid_facebook_token"
    
    # Create a valid token response for the first API call
    token_response = {
        "data": {
            "is_valid": True,
            "app_id": "123456789",
            "user_id": "9876543210"
        }
    }
    
    # Create a response with missing email for the second API call
    response_missing_email = {
        "id": "9876543210",
        "name": "Test Facebook User"
    }
    
    # Mock aiohttp.ClientSession
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Set up the mock to return different responses for different URLs
        def side_effect(*args, **kwargs):
            url = args[0]
            if "debug_token" in url:
                return MockResponse(token_response)
            else:
                return MockResponse(response_missing_email)
        
        mock_get.side_effect = side_effect
        
        # Execute & Verify
        with pytest.raises(SocialAuthError) as excinfo:
            await verify_facebook_token(token)
        
        # Verify error details
        assert "Email not provided by Facebook" in str(excinfo.value)
        
        # Verify both API calls were made
        assert mock_get.call_count == 2

@service_test
async def test_verify_social_token_google(mock_google_response):
    """Test verify_social_token with Google provider."""
    # Setup
    token = "valid_google_token"
    provider = "google"
    
    # Mock verify_google_token
    with patch("core.services.social.verify_google_token") as mock_verify:
        mock_user_info = SocialUserInfo(
            id=mock_google_response["sub"],
            email=mock_google_response["email"],
            name=mock_google_response["name"],
            picture=mock_google_response["picture"],
            provider="google"
        )
        mock_verify.return_value = mock_user_info
        
        # Execute
        result = await verify_social_token(provider, token)
        
        # Verify
        assert result is mock_user_info
        mock_verify.assert_called_once_with(token)

@service_test
async def test_verify_social_token_facebook(mock_facebook_response):
    """Test verify_social_token with Facebook provider."""
    # Setup
    token = "valid_facebook_token"
    provider = "facebook"
    
    # Mock verify_facebook_token
    with patch("core.services.social.verify_facebook_token") as mock_verify:
        mock_user_info = SocialUserInfo(
            id=mock_facebook_response["id"],
            email=mock_facebook_response["email"],
            name=mock_facebook_response["name"],
            picture=mock_facebook_response["picture"]["data"]["url"],
            provider="facebook"
        )
        mock_verify.return_value = mock_user_info
        
        # Execute
        result = await verify_social_token(provider, token)
        
        # Verify
        assert result is mock_user_info
        mock_verify.assert_called_once_with(token)

@service_test
async def test_verify_social_token_unsupported_provider():
    """Test verify_social_token with unsupported provider."""
    # Setup
    token = "some_token"
    provider = "unsupported_provider"
    
    # Execute & Verify
    with pytest.raises(SocialAuthError) as excinfo:
        await verify_social_token(provider, token)
    
    # Verify error details
    assert "Unsupported social provider" in str(excinfo.value)

@service_test
async def test_social_user_info_model():
    """Test SocialUserInfo model."""
    # Create model instance
    user_info = SocialUserInfo(
        id="12345",
        email="test@example.com",
        name="Test User",
        picture="https://example.com/test.jpg",
        provider="test_provider"
    )
    
    # Verify model properties
    assert user_info.id == "12345"
    assert user_info.email == "test@example.com"
    assert user_info.name == "Test User"
    assert user_info.picture == "https://example.com/test.jpg"
    assert user_info.provider == "test_provider"
    
    # Verify dict conversion
    user_dict = user_info.model_dump()
    assert user_dict["id"] == "12345"
    assert user_dict["email"] == "test@example.com"
    assert user_dict["provider"] == "test_provider" 