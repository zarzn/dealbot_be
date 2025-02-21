"""Test authentication endpoints."""

import pytest
from typing import Dict, AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.user import User, UserStatus
from core.utils.auth import get_password_hash

@pytest.mark.asyncio
class TestAuthEndpoints:
    """Test cases for authentication endpoints."""

    @pytest.fixture(autouse=True)
    async def setup(self, async_session: AsyncSession):
        """Setup test data."""
        self.session = async_session
        # Create test user for login tests
        self.test_user_data = {
            "email": "existing@example.com",
            "password": "StrongPass123!",
            "name": "Existing User"
        }
        hashed_password = get_password_hash(self.test_user_data["password"])
        test_user = User(
            email=self.test_user_data["email"],
            password=hashed_password,
            name=self.test_user_data["name"],
            status=UserStatus.ACTIVE.value
        )
        self.session.add(test_user)
        await self.session.commit()
        await self.session.refresh(test_user)
        self.test_user = test_user

    async def test_register_success(self, async_client: AsyncClient):
        """Test successful user registration."""
        user_data = {
            "email": "test@example.com",
            "password": "StrongPass123!",
            "name": "Test User"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=user_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["name"] == user_data["name"]
        assert "id" in data
        assert "password" not in data
        
        # Verify user in database
        db_user = await self.session.execute(
            select(User).where(User.email == user_data["email"])
        )
        db_user = db_user.scalar_one()
        assert db_user is not None
        assert db_user.email == user_data["email"]
        assert db_user.status == UserStatus.ACTIVE.value

    async def test_register_duplicate_email(self, async_client: AsyncClient):
        """Test registration with existing email."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json=self.test_user_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "email already exists" in data["error"].lower()

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
            "email": "test@example.com",
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

    async def test_login_success(self, async_client: AsyncClient):
        """Test successful login."""
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": self.test_user_data["email"],
                "password": self.test_user_data["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        """Test login with invalid credentials."""
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": self.test_user_data["email"],
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "invalid credentials" in data["error"].lower()

    async def test_login_inactive_user(self, async_client: AsyncClient):
        """Test login with inactive user."""
        # Deactivate user
        self.test_user.status = UserStatus.INACTIVE.value
        await self.session.commit()
        
        response = await async_client.post(
            "/api/v1/auth/login",
            data={
                "username": self.test_user_data["email"],
                "password": self.test_user_data["password"]
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "inactive" in data["error"].lower()

    async def test_refresh_token(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test token refresh."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != auth_headers["Authorization"].split()[1]

    async def test_logout(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test user logout."""
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "logged out" in data["message"].lower()
        
        # Verify token is invalidated
        protected_response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        assert protected_response.status_code == 401

    async def test_password_reset(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession
    ):
        """Test password reset flow."""
        # Request password reset
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 202

        # Set new password (would normally require token from email)
        response = await async_client.post(
            "/api/v1/auth/new-password",
            json={
                "token": "test_reset_token",
                "new_password": "NewStrongPass123!"
            }
        )
        assert response.status_code == 200 