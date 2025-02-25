"""Test authentication endpoints."""

import asyncio
import pytest
from typing import Dict, AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta
import jwt
from unittest.mock import AsyncMock, MagicMock, patch
from jwt.exceptions import ExpiredSignatureError

from core.models.user import User
from core.models.enums import UserStatus
from core.utils.auth import get_password_hash
from core.config import settings
from core.services.auth import blacklist_token, is_token_blacklisted
from core.exceptions.auth_exceptions import TokenError
from tests.mocks.redis_mock import get_redis_mock
from core.services.social import SocialUserInfo

@pytest.mark.asyncio
class TestAuthEndpoints:
    """Test cases for authentication endpoints."""

    @pytest.fixture
    async def redis_mock(self):
        """Create a mock Redis client for testing."""
        mock = get_redis_mock()
        await mock.init()
        return mock

    @pytest.fixture
    async def existing_user(self, async_session: AsyncSession) -> AsyncGenerator[User, None]:
        """Create a test user for login tests."""
        user_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "name": "Test User"
        }
        hashed_password = get_password_hash(user_data["password"])
        test_user = User(
            email=user_data["email"],
            password=hashed_password,
            name=user_data["name"],
            status=UserStatus.ACTIVE
        )
        async_session.add(test_user)
        await async_session.commit()
        await async_session.refresh(test_user)
        
        yield test_user
        
        # Cleanup after test
        await async_session.execute(
            delete(User).where(User.email == user_data["email"])
        )
        await async_session.commit()

    def create_test_token(self, user_id: str, token_type: str = "access", exp_delta: timedelta = None) -> str:
        """Create a test JWT token."""
        if exp_delta is None:
            exp_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        exp = datetime.utcnow() + exp_delta
        payload = {
            "sub": user_id,
            "type": token_type,
            "exp": exp.timestamp()
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,  # Use the test settings JWT secret
            algorithm=settings.JWT_ALGORITHM
        )

    async def verify_test_token(self, token: str) -> dict:
        """Verify a test JWT token."""
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,  # Use the test settings JWT secret
            algorithms=[settings.JWT_ALGORITHM]
        )

    async def test_register_success(self, async_client: AsyncClient, async_session: AsyncSession, redis_mock):
        """Test successful user registration."""
        with patch('core.utils.redis.get_redis_client', return_value=redis_mock):
            user_data = {
                "email": "new_user@example.com",
                "password": "StrongPass123!",
                "name": "Test User"
            }
            
            response = await async_client.post(
                "/api/v1/auth/register",
                json=user_data
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert "user" in data
            assert data["user"]["email"] == user_data["email"]
            assert data["user"]["name"] == user_data["name"]
            
            # Verify user in database
            result = await async_session.execute(
                select(User).where(User.email == user_data["email"])
            )
            db_user = result.scalar_one()
            assert db_user is not None
            assert db_user.email == user_data["email"]
            assert db_user.name == user_data["name"]
            assert db_user.status == UserStatus.ACTIVE
            assert not db_user.email_verified

    async def test_register_duplicate_email(self, async_client: AsyncClient, existing_user: User):
        """Test registration with existing email."""
        user_data = {
            "email": existing_user.email,
            "password": "StrongPass123!",
            "name": "Test User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=user_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error_code" in data["detail"]
        assert data["detail"]["error_code"] == "email_exists"

    async def test_register_invalid_email(self, async_client: AsyncClient):
        """Test registration with invalid email format."""
        invalid_data = {
            "email": "invalid-email",
            "password": "StrongPass123!",
            "name": "Test User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=invalid_data
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("email" in error["loc"] for error in data["detail"])

    async def test_register_weak_password(self, async_client: AsyncClient):
        """Test registration with weak password."""
        weak_password_data = {
            "email": "test2@example.com",
            "password": "weak",
            "name": "Test User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=weak_password_data
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("password" in error["loc"] for error in data["detail"])

    async def test_login_success(self, async_client: AsyncClient, existing_user: User, redis_mock):
        """Test successful login."""
        with patch('core.utils.redis.get_redis_client', return_value=redis_mock):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": existing_user.email,
                    "password": "testpassword123"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert "user" in data
            assert data["user"]["email"] == existing_user.email

    async def test_login_invalid_credentials(self, async_client: AsyncClient, existing_user: User):
        """Test login with invalid credentials."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data["detail"]
        assert data["detail"]["error_code"] == "invalid_credentials"

    async def test_login_inactive_user(self, async_client: AsyncClient, existing_user: User, async_session: AsyncSession):
        """Test login with inactive user."""
        # Deactivate user
        existing_user.status = UserStatus.INACTIVE
        await async_session.commit()
        
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data["detail"]
        assert data["detail"]["error_code"] == "inactive_user"

    async def test_refresh_token(self, async_client: AsyncClient, existing_user: User):
        """Test token refresh."""
        # First login to get tokens
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "testpassword123"
            }
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        # Try to refresh token
        refresh_response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]}
        )
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    async def test_refresh_token_invalid(self, async_client: AsyncClient):
        """Test refresh with invalid token."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "invalid token" in data["detail"].lower()

    async def test_logout(self, async_client: AsyncClient, existing_user: User):
        """Test user logout."""
        # First login to get token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "testpassword123"
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Logout
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "msg" in data
        assert "logged out" in data["msg"].lower()
        
        # Verify token is blacklisted
        response = await async_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert "token has been revoked" in response.json()["detail"].lower()

    async def test_password_reset_request(self, async_client: AsyncClient, existing_user: User):
        """Test password reset request."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={"email": existing_user.email}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "msg" in data
        assert "password reset email sent" in data["msg"].lower()

    async def test_password_reset_nonexistent_email(self, async_client: AsyncClient):
        """Test password reset with nonexistent email."""
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={"email": "nonexistent@example.com"}
        )
        
        # Should still return 202 for security
        assert response.status_code == 202
        data = response.json()
        assert "msg" in data
        assert "password reset email sent" in data["msg"].lower()

    async def test_password_reset_verify(self, async_client: AsyncClient, existing_user: User):
        """Test password reset verification."""
        # Create reset token
        token = jwt.encode(
            {
                "sub": str(existing_user.id),
                "type": "reset",
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        response = await async_client.post(
            "/api/v1/auth/reset-password/verify",
            json={
                "token": token,
                "password": "NewPassword123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "msg" in data
        assert "password successfully reset" in data["msg"].lower()
        
        # Verify new password works
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "NewPassword123!"
            }
        )
        assert login_response.status_code == 200

    async def test_verify_email(self, async_client: AsyncClient, existing_user: User, async_session: AsyncSession):
        """Test email verification."""
        # Create verification token
        token = jwt.encode(
            {
                "sub": str(existing_user.id),
                "type": "email_verification",
                "exp": datetime.utcnow() + timedelta(days=1)
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        response = await async_client.post(
            "/api/v1/auth/verify-email",
            json={"token": token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "msg" in data
        assert "email verified" in data["msg"].lower()
        
        # Verify user's email is marked as verified
        result = await async_session.execute(
            select(User).where(User.id == existing_user.id)
        )
        user = result.scalar_one()
        assert user.email_verified

    async def test_verify_email_invalid_token(self, async_client: AsyncClient, redis_mock):
        """Test email verification with invalid token."""
        with patch('core.utils.redis.get_redis_client', return_value=redis_mock):
            response = await async_client.post(
                "/api/v1/auth/verify-email",
                json={"token": "invalid-token"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "error_code" in data["detail"]
            assert data["detail"]["error_code"] == "invalid_token"

    async def test_magic_link_request(self, async_client: AsyncClient, existing_user: User):
        """Test magic link request."""
        response = await async_client.post(
            "/api/v1/auth/magic-link",
            json={"email": existing_user.email}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "msg" in data
        assert "magic link email sent" in data["msg"].lower()

    async def test_magic_link_verify(self, async_client: AsyncClient, existing_user: User):
        """Test magic link verification."""
        # Create magic link token
        token = jwt.encode(
            {
                "sub": str(existing_user.id),
                "type": "magic_link",
                "exp": datetime.utcnow() + timedelta(minutes=15)
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        response = await async_client.post(
            "/api/v1/auth/magic-link/verify",
            json={"token": token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == existing_user.email

    @pytest.mark.parametrize("provider", ["google", "facebook"])
    async def test_social_login_new_user(self, async_client: AsyncClient, redis_mock, mocker, provider: str):
        """Test social login for new user."""
        mock_user_info = SocialUserInfo(
            id="123",
            email="social@example.com",
            name="Social User",
            picture=None,
            provider=provider
        )
        mocker.patch(f'core.services.social.verify_{provider}_token', return_value=mock_user_info)
        
        with patch('core.utils.redis.get_redis_client', return_value=redis_mock):
            response = await async_client.post(
                "/api/v1/auth/social",
                json={
                    "provider": provider,
                    "token": "test-token"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert "user" in data
            assert data["user"]["email"] == mock_user_info.email
            assert data["user"]["name"] == mock_user_info.name

    @pytest.mark.parametrize("provider", ["google", "facebook"])
    async def test_social_login_existing_user(
        self,
        async_client: AsyncClient,
        existing_user: User,
        provider: str,
        mocker,
        async_session: AsyncSession
    ):
        """Test social login for existing user."""
        # Update existing user with social info
        existing_user.social_provider = provider
        existing_user.social_id = "123"
        await async_session.commit()
        
        # Mock social token verification
        mock_user_info = SocialUserInfo(
            id="123",
            email=existing_user.email,
            name=existing_user.name,
            provider=provider
        )
        mocker.patch(
            "core.services.social.verify_social_token",
            return_value=mock_user_info
        )
        
        response = await async_client.post(
            "/api/v1/auth/social",
            json={
                "provider": provider,
                "token": "valid_token"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == existing_user.email
        assert data["user"]["social_provider"] == provider
        assert data["user"]["social_id"] == "123"

@pytest.mark.asyncio
async def test_blacklist_token(redis_mock):
    """Test token blacklisting."""
    token = jwt.encode(
        {"sub": "test-user-id", "exp": datetime.utcnow().timestamp() + 3600},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    # Blacklist token
    await blacklist_token(token, redis_mock)
    
    # Check if token is blacklisted
    is_blacklisted = await is_token_blacklisted(token, redis_mock)
    assert is_blacklisted is True

@pytest.mark.asyncio
async def test_token_expiry(redis_mock):
    """Test token expiration."""
    token = jwt.encode(
        {"sub": "test-user-id", "exp": datetime.utcnow().timestamp() + 3600},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    # Blacklist token with expiry
    await blacklist_token(token, redis_mock)
    
    # Check if token is blacklisted
    is_blacklisted = await is_token_blacklisted(token, redis_mock)
    assert is_blacklisted is True

@pytest.mark.asyncio
async def test_token_blacklist_flow(async_client: AsyncClient, existing_user: User, redis_mock):
    """Test complete token blacklist flow with login and logout."""
    with patch('core.utils.redis.get_redis_client', return_value=redis_mock):
        # Login to get token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": existing_user.email,
                "password": "testpassword123"
            }
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        # Use token for authenticated request
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        profile_response = await async_client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == 200
        
        # Logout to blacklist token
        logout_response = await async_client.post(
            "/api/v1/auth/logout",
            headers=headers
        )
        assert logout_response.status_code == 200
        
        # Try to use blacklisted token
        profile_response = await async_client.get("/api/v1/users/me", headers=headers)
        assert profile_response.status_code == 401

@pytest.mark.asyncio
async def test_token_blacklist_error_handling(redis_mock):
    """Test error handling in token blacklist operations."""
    token = "test_token"
    
    # Test blacklisting with invalid token
    with pytest.raises(TokenError):
        await blacklist_token("invalid_token", redis_mock)
    
    # Test checking blacklist with Redis error
    redis_mock.is_token_blacklisted = AsyncMock(side_effect=Exception("Redis error"))
    with pytest.raises(TokenError):
        await is_token_blacklisted(token, redis_mock) 