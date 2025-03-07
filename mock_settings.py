"""Create a mock Settings class for testing."""

import os
import sys
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Set environment variables for testing
os.environ["TESTING"] = "true"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = ""
os.environ["host"] = "localhost"
os.environ["hosts"] = '["localhost"]'

# Create a mock Settings class
class MockSettings(BaseModel):
    """Mock Settings class for testing."""
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    host: str = "localhost"
    hosts: List[str] = ["localhost"]
    
    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:12345678@localhost:5432/agentic_deals_test"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "agentic_deals_test"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    
    # JWT settings
    JWT_SECRET_KEY: str = "test-secret-key"
    JWT_SECRET: str = "test-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application settings
    APP_NAME: str = "AI Agentic Deals"
    APP_VERSION: str = "1.0.0"
    APP_ENVIRONMENT: str = "test"
    TESTING: bool = True
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # LLM settings
    OPENAI_API_KEY: str = "test_openai_api_key"
    GOOGLE_API_KEY: str = "test_google_api_key"
    DEEPSEEK_API_KEY: str = "test_deepseek_api_key"

# Create a mock settings instance
mock_settings = MockSettings()

# Print the mock settings
print("Mock Settings:")
print(f"host: {mock_settings.host}")
print(f"hosts: {mock_settings.hosts}")
print(f"REDIS_URL: {mock_settings.REDIS_URL}")
print(f"REDIS_HOST: {mock_settings.REDIS_HOST}")
print(f"DATABASE_URL: {mock_settings.DATABASE_URL}")

# Monkey patch the settings module
sys.modules['core.config.settings'] = mock_settings
sys.modules['core.config'] = mock_settings

print("\nSettings module patched successfully!")

# Try to import the settings
try:
    from core.config import settings
    print("\nImported Settings:")
    print(f"host: {settings.host}")
    print(f"hosts: {settings.hosts}")
    print(f"REDIS_URL: {settings.REDIS_URL}")
    print(f"REDIS_HOST: {settings.REDIS_HOST}")
except Exception as e:
    print(f"\nError importing settings: {str(e)}")
    import traceback
    traceback.print_exc() 