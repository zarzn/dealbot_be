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
# Use only hosts array for Redis connection validation
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
    # Use only hosts array for Redis connection validation
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

# Create a mock Settings class using Pydantic v1 style to avoid plugin issues
try:
    # Try to import from pydantic.v1 first (for Pydantic v2)
    from pydantic.v1 import BaseModel, Field
except ImportError:
    # Fall back to regular import (for Pydantic v1)
    from pydantic import BaseModel, Field

class MockSettings:
    """Mock Settings class for testing using a simple object instead of a Pydantic model."""
    # Redis settings
    REDIS_URL = "redis://localhost:6379/0"
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_PASSWORD = ""
    # Use only hosts array for Redis connection validation
    hosts = ["localhost"]
    
    # Database settings
    DATABASE_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/deals_test"
    POSTGRES_USER = "postgres"
    POSTGRES_PASSWORD = "12345678"
    POSTGRES_DB = "deals_test"
    POSTGRES_HOST = "localhost"
    POSTGRES_PORT = 5432
    
    # Database pool settings
    DB_POOL_SIZE = 5
    DB_MAX_OVERFLOW = 10
    DB_POOL_TIMEOUT = 30
    DB_POOL_RECYCLE = 1800
    DB_ECHO = True
    DB_STATEMENT_TIMEOUT = 30
    DB_IDLE_TIMEOUT = 300
    DB_MAX_RETRIES = 3
    DB_RETRY_DELAY = 1.0
    
    # JWT settings
    JWT_SECRET_KEY = "test-secret-key"
    JWT_SECRET = "test-jwt-secret-key"
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # Application settings
    APP_NAME = "AI Agentic Deals"
    APP_VERSION = "1.0.0"
    APP_ENVIRONMENT = "test"
    TESTING = True
    DEBUG = True
    
    # API settings
    API_V1_STR = "/api/v1"
    API_PREFIX = "/api/v1"
    API_DESCRIPTION = "AI Agentic Deals System API"
    
    # LLM settings
    OPENAI_API_KEY = "test_openai_api_key"
    GOOGLE_API_KEY = "test_google_api_key"
    DEEPSEEK_API_KEY = "test_deepseek_api_key"
    
    # Logging settings
    LOG_LEVEL = logging.DEBUG
    
    # Blockchain settings
    SOL_NETWORK_RPC = "https://api.devnet.solana.com"
    TOKEN_CONTRACT_ADDRESS = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    TOKEN_REQUIRED_BALANCE = Decimal("100.0")
    TOKEN_SEARCH_COST = Decimal("5.0")
    
    # Email settings
    EMAIL_TEMPLATES_DIR = str(backend_dir / "core" / "templates" / "email")
    EMAIL_BACKEND = "core.services.email.backends.console.ConsoleEmailBackend"
    EMAIL_FROM = "test@example.com"
    EMAIL_HOST = "localhost"
    EMAIL_PORT = 25
    EMAIL_USE_TLS = False
    EMAIL_HOST_USER = ""
    EMAIL_HOST_PASSWORD = ""
    
    # Firebase Cloud Messaging settings
    FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send"
    FCM_API_KEY = "test_fcm_api_key"
    FCM_SENDER_ID = "test_fcm_sender_id"
    FCM_APP_ID = "test_fcm_app_id"
    FCM_PROJECT_ID = "test_fcm_project_id"
    FCM_STORAGE_BUCKET = "test_fcm_storage_bucket"
    FCM_SERVICE_ACCOUNT_KEY = {}
    
    # Additional settings that might be needed
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
    STATIC_DIR = str(backend_dir / "static")
    MEDIA_DIR = str(backend_dir / "media")
    TEMPLATES_DIR = str(backend_dir / "templates")
    ALLOWED_HOSTS = ["*"]
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER = str(backend_dir / "uploads")
    TEMP_FOLDER = str(backend_dir / "temp")
    DEFAULT_PAGINATION_LIMIT = 100
    DEFAULT_PAGINATION_OFFSET = 0
    TOKEN_ANALYSIS_COST = Decimal("10.0")
    TOKEN_PREDICTION_COST = Decimal("15.0")
    TOKEN_ALERT_COST = Decimal("2.0")
    
    # Goal settings
    MAX_GOAL_PRICE = 10000.0
    MAX_GOAL_DEADLINE_DAYS = 90
    
    # Cache settings
    MARKET_CACHE_TTL = 3600
    PRODUCT_CACHE_TTL = 1800
    TOKEN_CACHE_TTL = 3000
    BALANCE_CACHE_TTL = 1800
    GOAL_CACHE_TTL = 3600
    
    # Market rate limits
    AMAZON_RATE_LIMIT = 50
    WALMART_RATE_LIMIT = 50
    EBAY_RATE_LIMIT = 50
    
    # Token settings
    TOKEN_DECIMALS = 9
    
    # Social auth settings
    FACEBOOK_APP_TOKEN = "test-facebook-app-token"
    GOOGLE_CLIENT_ID = "test-google-client-id"
    GOOGLE_CLIENT_SECRET = "test-google-client-secret"
    
    # Add any other required settings
    SECRET_KEY = "test-secret-key"
    CORS_ORIGINS = ["*"]
    
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
        
    # Add host property to maintain compatibility with Redis client code
    # that might use settings.host
    @property
    def host(self) -> str:
        """Get Redis host from hosts array."""
        return self.hosts[0] if self.hosts else "localhost"

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
print("Fixing the Base class registry issue...")

# Import both Base classes
from core.database import Base as DatabaseBase
from core.models.base import Base as ModelsBase

# Import all models to ensure they are registered with Base.metadata
from core.models.user import User
from core.models.deal import Deal, PriceHistory 
from core.models.deal_token import DealToken
from core.models.tracked_deal import TrackedDeal
from core.models.market import Market
from core.models.goal import Goal
from core.models.auth_token import AuthToken
from core.models.token import Token
from core.models.token_transaction import TokenTransaction
from core.models.token_balance import TokenBalance, TokenBalanceHistory
from core.models.token_pricing import TokenPricing
from core.models.token_wallet import TokenWallet, WalletTransaction
from core.models.agent import Agent
from core.models.chat import Chat, ChatMessage
from core.models.chat_context import ChatContext
from core.models.notification import Notification
from core.models.price_tracking import PriceTracker, PricePoint
from core.models.price_prediction import PricePrediction, ModelMetrics
from core.models.deal_score import DealScore, DealMatch
from core.models.deal_interaction import DealInteraction
from core.models.user_preferences import UserPreferences

# Print registered tables in each Base's metadata
print("\nRegistered tables in DatabaseBase.metadata:")
db_tables = sorted([table.name for table in DatabaseBase.metadata.tables.values()])
for table in db_tables:
    print(f"  - {table}")

print("\nRegistered tables in ModelsBase.metadata:")
model_tables = sorted([table.name for table in ModelsBase.metadata.tables.values()])
for table in model_tables:
    print(f"  - {table}")

# Fix the issue by copying table metadata from ModelsBase to DatabaseBase
if 'agents' not in DatabaseBase.metadata.tables:
    print("\nThe 'agents' table is not registered with DatabaseBase.metadata")
    print("Fixing by copying model metadata from ModelsBase to DatabaseBase...")
    
    # Copy all tables from ModelsBase to DatabaseBase
    for table_name, table in ModelsBase.metadata.tables.items():
        if table_name not in DatabaseBase.metadata.tables:
            # Clone the table into DatabaseBase.metadata
            DatabaseBase.metadata._add_table(table_name, table.schema, table)
            print(f"  - Added {table_name} to DatabaseBase.metadata")

# Verify that 'agents' table is now in DatabaseBase.metadata
if 'agents' in DatabaseBase.metadata.tables:
    print("\nVerification: 'agents' table is now registered with DatabaseBase.metadata")
else:
    print("\nWARNING: 'agents' table is still not registered with DatabaseBase.metadata")
    
# Print updated tables in DatabaseBase.metadata
print("\nUpdated tables in DatabaseBase.metadata:")
db_tables = sorted([table.name for table in DatabaseBase.metadata.tables.values()])
for table in db_tables:
    print(f"  - {table}")

# Verify that 'chat_contexts' table is now in DatabaseBase.metadata
if 'chat_contexts' in DatabaseBase.metadata.tables:
    print("\nVerification: 'chat_contexts' table is now registered with DatabaseBase.metadata")
else:
    print("\nWARNING: 'chat_contexts' table is still not registered with DatabaseBase.metadata")

print("\nBase class registry issues should now be fixed.") 