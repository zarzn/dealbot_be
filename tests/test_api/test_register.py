"""Test registration endpoints."""

import pytest
from uuid import UUID
from datetime import datetime
from httpx import AsyncClient
from typing import AsyncGenerator

from core.database import get_async_db_session, AsyncSessionLocal

# API Configuration
BASE_URL = "http://localhost:8000"

@pytest.fixture
def headers():
    return {
        "Content-Type": "application/json"
    }

@pytest.fixture
def valid_user_data():
    return {
        "email": "test@example.com",
        "password": "Test123!@#",
        "referral_code": "TEST123"
    }

@pytest.mark.asyncio
async def test_successful_registration(async_client: AsyncClient):
    """Test successful user registration with valid data."""
    headers = {'Content-Type': 'application/json'}
    valid_user_data = {
        'email': 'test@example.com',
        'password': 'Test123!@#',
        'referral_code': 'TEST123'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=valid_user_data, headers=headers)
    assert response.status_code == 201
    assert "id" in response.json()
    assert "email" in response.json()
    assert response.json()["email"] == valid_user_data["email"]

@pytest.mark.asyncio
async def test_duplicate_email(async_client: AsyncClient):
    """Test registration with a duplicate email."""
    headers = {'Content-Type': 'application/json'}
    valid_user_data = {
        'email': 'test@example.com',
        'password': 'Test123!@#',
        'referral_code': 'TEST123'
    }
    
    # First registration
    await async_client.post("/api/v1/auth/register", json=valid_user_data, headers=headers)
    
    # Second registration with same email
    response = await async_client.post("/api/v1/auth/register", json=valid_user_data, headers=headers)
    assert response.status_code == 400
    assert "error" in response.json()
    assert "email already exists" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_invalid_email_format(async_client: AsyncClient):
    """Test registration with an invalid email format."""
    headers = {'Content-Type': 'application/json'}
    invalid_user_data = {
        'email': 'invalid-email',
        'password': 'Test123!@#'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=invalid_user_data, headers=headers)
    assert response.status_code == 422
    assert "error" in response.json()
    assert "email" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_weak_password(async_client: AsyncClient):
    """Test registration with a weak password."""
    headers = {'Content-Type': 'application/json'}
    invalid_user_data = {
        'email': 'test@example.com',
        'password': 'weak'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=invalid_user_data, headers=headers)
    assert response.status_code == 422
    assert "error" in response.json()
    assert "password" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_invalid_referral_code(async_client: AsyncClient):
    """Test registration with an invalid referral code."""
    headers = {'Content-Type': 'application/json'}
    invalid_user_data = {
        'email': 'test@example.com',
        'password': 'Test123!@#',
        'referral_code': 'INVALID'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=invalid_user_data, headers=headers)
    assert response.status_code == 400
    assert "error" in response.json()
    assert "referral code" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_missing_required_fields(async_client: AsyncClient):
    """Test registration with missing required fields."""
    headers = {'Content-Type': 'application/json'}
    invalid_user_data = {
        'email': 'test@example.com'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=invalid_user_data, headers=headers)
    assert response.status_code == 422
    assert "error" in response.json()
    assert "password" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_registration_with_only_required_fields(async_client: AsyncClient):
    """Test registration with only required fields."""
    headers = {'Content-Type': 'application/json'}
    valid_user_data = {
        'email': 'test@example.com',
        'password': 'Test123!@#'
    }
    
    response = await async_client.post("/api/v1/auth/register", json=valid_user_data, headers=headers)
    assert response.status_code == 201
    assert "id" in response.json()
    assert "email" in response.json()
    assert response.json()["email"] == valid_user_data["email"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 