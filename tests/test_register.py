import pytest
import requests
import json
from uuid import UUID
from datetime import datetime

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

def test_successful_registration(headers, valid_user_data):
    """Test successful user registration with valid data"""
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=valid_user_data
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert data["email"] == valid_user_data["email"]
    try:
        UUID(data["id"])
    except ValueError:
        pytest.fail("Invalid UUID format for user ID")

def test_duplicate_email(headers, valid_user_data):
    """Test registration with duplicate email"""
    # First registration
    requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=valid_user_data
    )
    
    # Second registration with same email
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=valid_user_data
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "email already exists" in data["error"]["message"].lower()

def test_invalid_email_format(headers):
    """Test registration with invalid email format"""
    invalid_data = {
        "email": "invalid-email",
        "password": "Test123!@#",
        "referral_code": "TEST123"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=invalid_data
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "email" in data["error"]["message"].lower()

def test_weak_password(headers):
    """Test registration with weak password"""
    weak_password_data = {
        "email": "test@example.com",
        "password": "weak",
        "referral_code": "TEST123"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=weak_password_data
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "password" in data["error"]["message"].lower()

def test_invalid_referral_code(headers):
    """Test registration with invalid referral code"""
    invalid_referral_data = {
        "email": "test@example.com",
        "password": "Test123!@#",
        "referral_code": "INVALID"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=invalid_referral_data
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "referral code" in data["error"]["message"].lower()

def test_missing_required_fields(headers):
    """Test registration with missing required fields"""
    incomplete_data = {
        "email": "test@example.com"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=incomplete_data
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "password" in data["error"]["message"].lower()

def test_registration_with_only_required_fields(headers):
    """Test registration with only required fields"""
    minimal_data = {
        "email": "minimal@example.com",
        "password": "Test123!@#"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/users/register",
        headers=headers,
        json=minimal_data
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert data["email"] == minimal_data["email"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 