"""Patch the Settings class to fix validation issues.

This script should be imported before any other module that imports Settings.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from decimal import Decimal

# Set testing flags in environment
os.environ["TESTING"] = "true"
os.environ["SKIP_TOKEN_VERIFICATION"] = "true"

# Set environment variables for Redis
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = ""
os.environ["host"] = "localhost"
os.environ["hosts"] = '["localhost"]'

# Load environment variables from .env.test file
from dotenv import load_dotenv
backend_dir = Path(__file__).parent
env_test_file = backend_dir / '.env.test'
if env_test_file.exists():
    print(f"Loading test environment from: {env_test_file}")
    load_dotenv(env_test_file, override=True)
else:
    print(f"Warning: {env_test_file} not found, using default test configuration")
    # Set default test environment variables if .env.test is not found
    os.environ.setdefault("APP_NAME", "AI Agentic Deals System Test")
    os.environ.setdefault("POSTGRES_USER", "postgres")
    os.environ.setdefault("POSTGRES_PASSWORD", "12345678")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("POSTGRES_DB", "deals_test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("REDIS_PASSWORD", "")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("host", "localhost")  # Required by Pydantic
    os.environ.setdefault("hosts", '["localhost"]')  # Required by Pydantic
    os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_for_testing_only")
    os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
    os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key")
    os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")
    os.environ.setdefault("SOL_NETWORK_RPC", "https://api.devnet.solana.com")
    os.environ.setdefault("TOKEN_CONTRACT_ADDRESS", "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    os.environ.setdefault("TOKEN_REQUIRED_BALANCE", "100.0")
    os.environ.setdefault("TOKEN_SEARCH_COST", "5.0")
    os.environ.setdefault("EMAIL_TEMPLATES_DIR", str(backend_dir / "core" / "templates" / "email"))
    os.environ.setdefault("EMAIL_BACKEND", "core.services.email.backends.console.ConsoleEmailBackend")
    os.environ.setdefault("EMAIL_FROM", "test@example.com")
    os.environ.setdefault("EMAIL_HOST", "localhost")
    os.environ.setdefault("EMAIL_PORT", "25")
    os.environ.setdefault("EMAIL_USE_TLS", "False")
    os.environ.setdefault("EMAIL_HOST_USER", "")
    os.environ.setdefault("EMAIL_HOST_PASSWORD", "")
    os.environ.setdefault("FCM_ENDPOINT", "https://fcm.googleapis.com/fcm/send")
    os.environ.setdefault("FCM_API_KEY", "test_fcm_api_key")
    os.environ.setdefault("FCM_SENDER_ID", "test_fcm_sender_id")
    os.environ.setdefault("FCM_APP_ID", "test_fcm_app_id")
    os.environ.setdefault("FCM_PROJECT_ID", "test_fcm_project_id")
    os.environ.setdefault("FCM_STORAGE_BUCKET", "test_fcm_storage_bucket")
    os.environ.setdefault("FCM_SERVICE_ACCOUNT_KEY", "{}")

print("Environment variables set for testing")

# Create a mock Settings class
from pydantic import BaseModel, Field

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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:12345678@localhost:5432/deals_test"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "deals_test"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    
    # Database pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = True
    DB_STATEMENT_TIMEOUT: int = 30
    DB_IDLE_TIMEOUT: int = 300
    DB_MAX_OVERFLOW: int = 10
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: float = 1.0
    
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
    DEBUG: bool = True
    
    # API settings
    API_V1_STR: str = "/api/v1"
    API_PREFIX: str = "/api/v1"
    API_DESCRIPTION: str = "AI Agentic Deals System API"
    
    # LLM settings
    OPENAI_API_KEY: str = "test_openai_api_key"
    GOOGLE_API_KEY: str = "test_google_api_key"
    DEEPSEEK_API_KEY: str = "test_deepseek_api_key"
    
    # Logging settings
    LOG_LEVEL: int = logging.DEBUG
    
    # Blockchain settings
    SOL_NETWORK_RPC: str = "https://api.devnet.solana.com"
    TOKEN_CONTRACT_ADDRESS: str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    TOKEN_REQUIRED_BALANCE: Decimal = Decimal("100.0")
    TOKEN_SEARCH_COST: Decimal = Decimal("5.0")
    
    # Email settings
    EMAIL_TEMPLATES_DIR: str = str(backend_dir / "core" / "templates" / "email")
    EMAIL_BACKEND: str = "core.services.email.backends.console.ConsoleEmailBackend"
    EMAIL_FROM: str = "test@example.com"
    EMAIL_HOST: str = "localhost"
    EMAIL_PORT: int = 25
    EMAIL_USE_TLS: bool = False
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""
    
    # Firebase Cloud Messaging settings
    FCM_ENDPOINT: str = "https://fcm.googleapis.com/fcm/send"
    FCM_API_KEY: str = "test_fcm_api_key"
    FCM_SENDER_ID: str = "test_fcm_sender_id"
    FCM_APP_ID: str = "test_fcm_app_id"
    FCM_PROJECT_ID: str = "test_fcm_project_id"
    FCM_STORAGE_BUCKET: str = "test_fcm_storage_bucket"
    FCM_SERVICE_ACCOUNT_KEY: Dict[str, Any] = {}
    
    # Additional settings that might be needed
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    STATIC_DIR: str = str(backend_dir / "static")
    MEDIA_DIR: str = str(backend_dir / "media")
    TEMPLATES_DIR: str = str(backend_dir / "templates")
    ALLOWED_HOSTS: List[str] = ["*"]
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER: str = str(backend_dir / "uploads")
    TEMP_FOLDER: str = str(backend_dir / "temp")
    DEFAULT_PAGINATION_LIMIT: int = 100
    DEFAULT_PAGINATION_OFFSET: int = 0
    TOKEN_ANALYSIS_COST: Decimal = Decimal("10.0")
    TOKEN_PREDICTION_COST: Decimal = Decimal("15.0")
    TOKEN_ALERT_COST: Decimal = Decimal("2.0")
    
    # Add any other required settings
    SECRET_KEY: str = "test-secret-key"
    CORS_ORIGINS: List[str] = ["*"]
    
    # Add computed properties
    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL."""
        return str(self.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get SQLAlchemy database URI."""
        return str(self.DATABASE_URL)
    
    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL."""
        return str(self.REDIS_URL)
    
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL."""
        return str(self.REDIS_URL)

# Create a mock settings instance
settings = MockSettings()

# Create a mock get_settings function
def get_settings():
    """Get settings instance."""
    return settings

# Monkey patch the settings module
# First, create a mock module
class MockModule:
    """Mock module for settings."""
    def __init__(self):
        self.settings = settings
        self.get_settings = get_settings
        self.Settings = MockSettings

# Create mock modules
mock_settings_module = MockModule()
mock_config_module = MockModule()

# Patch the modules
sys.modules['core.config.settings'] = mock_settings_module
sys.modules['core.config'] = mock_config_module

print("Settings module patched successfully") 