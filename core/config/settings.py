"""Application settings module.

This module provides centralized configuration management for the AI Agentic Deals System.
All application settings are defined here and can be overridden using environment variables.

Environment Variable Precedence:
1. OS Environment Variables (Highest Priority)
   - Set via export/set commands
   - Set in deployment environment
   - Example: export DATABASE_URL="postgresql://user:pass@host:5432/db"

2. Environment-Specific .env Files
   - .env.production (Production environment)
   - .env.test (Testing environment)
   - .env.development (Development environment)

3. Default .env File
   - .env file in project root
   - General development settings

4. Settings Class Defaults (Lowest Priority)
   - Default values defined in this Settings class
   - Fallback values if not set in any above source

Usage:
    from core.config import settings
    
    # Access settings
    database_url = settings.DATABASE_URL
    redis_host = settings.REDIS_HOST
    
    # Use in database connection
    engine = create_async_engine(str(settings.DATABASE_URL))
    
    # Use in Redis connection
    redis = Redis.from_url(str(settings.REDIS_URL))

Environment Variables:
    Settings can be overridden using environment variables with the same name:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
    export REDIS_URL="redis://localhost:6379/0"

Configuration Files:
    - Development: .env.development
    - Production: .env.production
    - Testing: .env.test
    - Default: .env

Security Note:
    Sensitive settings (passwords, API keys) should always be provided via
    environment variables in production, never hardcoded in this file.

Environment Variable Rules:
1. Variable names are case-sensitive and match the Settings class field names
2. Boolean values can be set using "1", "true", "yes", "on" for True
3. List/array values can be set using comma-separated strings
4. Nested dictionary values can be set using JSON strings
5. Secret values (passwords, keys) should use SecretStr type for security
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Set
from functools import lru_cache
from pydantic import (
    PostgresDsn,
    RedisDsn,
    SecretStr,
    Field,
    model_validator,
    computed_field,
    HttpUrl
)
from pydantic_settings import BaseSettings
import sys

# Get the base directory
_BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Debug print statements - limited to non-sensitive information
print("DEBUG: Loading environment variables in settings.py")
# Remove sensitive environment variable printing
# Environment detection only
print(f"DEBUG: Environment: {os.environ.get('APP_ENVIRONMENT', 'development')}")

class Settings(BaseSettings):
    """Application settings.
    
    This class defines all configuration settings for the application.
    Settings are loaded from environment variables and .env files.
    """

    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = Field(default=24)

    # Application settings
    APP_NAME: str = Field(default="AI Agentic Deals", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    APP_ENVIRONMENT: str = Field(default="development", description="Application environment")
    APP_HOST: str = Field(default="0.0.0.0", description="Application host")
    APP_PORT: int = Field(default=8000, description="Application port")
    APP_WORKERS: int = Field(default=4, description="Number of application workers")

    # Testing settings
    TESTING: bool = Field(default=True, description="Testing mode")
    SKIP_TOKEN_VERIFICATION: bool = Field(default=False, description="Skip token verification")
    
    # System user ID for operations that don't have a specific user
    SYSTEM_USER_ID: str = Field(default="00000000-0000-4000-a000-000000000001", description="System admin user ID")
    TEST_USER_ID: str = Field(default="00000000-0000-4000-a000-000000000001", description="Test user ID")

    # Base directory
    BASE_DIR: str = str(_BASE_DIR)

    # Logging settings
    LOG_LEVEL: Union[str, int] = Field(default=logging.INFO, description="Logging level")
    LOG_FORMAT: str = Field(default="%(asctime)s %(levelname)s %(message)s", description="Log format")
    LOG_FILE: Optional[str] = Field(default=None, description="Log file path")
    LOG_REQUEST_BODY: bool = Field(default=True, description="Log request bodies")
    LOG_RESPONSE_BODY: bool = Field(default=False, description="Log response bodies")
    LOG_HEADERS: bool = Field(default=True, description="Log request/response headers")
    LOG_QUERY_PARAMS: bool = Field(default=True, description="Log query parameters")
    LOG_EXCLUDE_PATHS: List[str] = Field(
        default=["/health", "/metrics"],
        description="Paths to exclude from logging"
    )

    # Database settings
    DATABASE_URL: Optional[PostgresDsn] = Field(
        default=None,  # Will be built by validator based on environment
        description="Database URL"
    )
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="12345678")
    POSTGRES_DB: str = Field(default="agentic_deals")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: str = Field(default="5432")

    # Database pool settings
    DB_POOL_SIZE: int = Field(default=8, description="Database pool size - reduced to prevent connection exhaustion")
    DB_MAX_OVERFLOW: int = Field(default=8, description="Maximum pool overflow - reduced to prevent connection exhaustion")
    DB_POOL_TIMEOUT: int = Field(default=15, description="Pool timeout in seconds - reduced to fail faster")
    DB_POOL_RECYCLE: int = Field(default=600, description="Connection recycle time in seconds - reduced to recycle more frequently")
    DB_MAX_RETRIES: int = Field(default=3, description="Maximum connection retry attempts")
    DB_RETRY_DELAY: float = Field(default=1.0, description="Delay between retries in seconds")
    DB_IDLE_TIMEOUT: int = Field(default=120, description="Idle connection timeout in seconds - reduced to close idle connections faster")
    DB_ECHO: bool = Field(default=True, description="Enable SQL query logging")

    # Redis settings
    REDIS_URL: Optional[RedisDsn] = Field(
        default=None,  # Will be built by validator based on environment
        description="Redis URL"
    )
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="your_redis_password")
    REDIS_MAX_CONNECTIONS: int = Field(default=10)
    REDIS_SOCKET_TIMEOUT: int = Field(default=5)
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=5)
    REDIS_SOCKET_KEEPALIVE: bool = Field(default=True)
    REDIS_SOCKET_KEEPALIVE_OPTIONS: Dict[str, Union[str, int]] = Field(
        default={
            'TCP_KEEPIDLE': 60,
            'TCP_KEEPINTVL': 10,
            'TCP_KEEPCNT': 3
        }
    )
    REDIS_RETRY_ON_TIMEOUT: bool = Field(default=True)
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    REDIS_ENCODING: str = Field(default="utf-8")
    REDIS_RETRY_ON_ERROR: bool = Field(default=True)
    REDIS_MAX_RETRIES: int = Field(default=3)
    REDIS_RETRY_DELAY: float = Field(default=1.0)
    REDIS_RETRY_MAX_DELAY: float = Field(default=5.0)
    REDIS_RETRY_JITTER: bool = Field(default=True)
    hosts: List[str] = Field(default=["localhost"])
    host: str = Field(default="localhost")

    # JWT settings
    JWT_SECRET_KEY: SecretStr = Field(default="test-secret-key")
    JWT_SECRET: SecretStr = Field(default="test-jwt-secret-key")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = Field(default=7 * 24 * 60)

    # NextAuth settings
    NEXTAUTH_SECRET: SecretStr = Field(default="test-nextauth-secret-key")

    # API settings
    API_V1_STR: str = Field(default="/api/v1")
    API_V1_PREFIX: str = Field(default="/api/v1")
    API_PREFIX: str = Field(default="/api/v1")
    API_VERSION: str = Field(default="v1")
    API_TITLE: str = Field(default="AI Agentic Deals API")
    API_DESCRIPTION: str = Field(default="AI-powered deal monitoring system")
    API_DOCS_URL: str = Field(default="/docs")
    API_REDOC_URL: str = Field(default="/redoc")
    API_OPENAPI_URL: str = Field(default="/openapi.json")
    API_ROOT_PATH: str = Field(default="")
    API_DEBUG: bool = Field(default=False)

    # Site settings
    SITE_URL: str = Field(default="http://localhost:3000", description="Frontend site URL")

    # Security settings
    SECRET_KEY: SecretStr = Field(default="test-secret-key")
    CORS_ORIGINS: List[str] = Field(default=["*", "https://d3irpl0o2ddv9y.cloudfront.net"])
    SENSITIVE_HEADERS: Set[str] = Field(
        default={
            "authorization", "cookie", "x-api-key",
            "x-csrf-token", "x-xsrf-token"
        },
        description="Headers to be masked in logs"
    )

    # Authentication settings
    AUTH_EXCLUDE_PATHS: List[str] = Field(
        default=[
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/magic-link",
            "/api/v1/auth/social",
            "/api/v1/docs",
            "/api/v1/openapi.json",
            "/api/v1/health",
            "/api/v1/metrics",
            "/api/v1/deals/public",
            "/api/v1/deals/open-public",
            "/api/v1/deals/share/auth-debug",
            "/api/v1/deals/share/no-auth-test"
        ]
    )

    # Rate limiting settings
    RATE_LIMIT_PER_SECOND: int = Field(default=30)
    RATE_LIMIT_PER_MINUTE: int = Field(default=500)
    RATE_LIMIT_WINDOW: int = Field(default=60)  # Window in seconds
    RATE_LIMIT_BURST: int = Field(default=50)  # Burst limit

    # External API settings
    SCRAPER_API_KEY: SecretStr = Field(default="test-scraper-key")
    SCRAPER_API_BASE_URL: str = Field(default="https://api.scraperapi.com")
    SCRAPER_API_CONCURRENT_LIMIT: int = Field(default=10)
    SCRAPER_API_REQUESTS_PER_SECOND: int = Field(default=5)
    SCRAPER_API_MONTHLY_LIMIT: int = Field(default=10000)
    SCRAPER_API_TIMEOUT: int = Field(default=30)
    SCRAPER_API_CACHE_TTL: int = Field(default=3600)

    # Market integration settings
    AMAZON_ACCESS_KEY: Optional[SecretStr] = Field(default=None, description="Amazon API access key")
    AMAZON_SECRET_KEY: Optional[SecretStr] = Field(default=None, description="Amazon API secret key")
    AMAZON_PARTNER_TAG: Optional[str] = Field(default=None, description="Amazon partner tag")
    AMAZON_COUNTRY: str = Field(default="US", description="Amazon marketplace country")
    WALMART_CLIENT_ID: Optional[SecretStr] = Field(default=None, description="Walmart API client ID")
    WALMART_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="Walmart API client secret")
    MARKET_DEFAULT_RATE_LIMIT: int = Field(default=50, description="Default market rate limit")
    MARKET_TIMEOUT: int = Field(default=30, description="Market request timeout in seconds")

    # LLM settings
    DEEPSEEK_API_KEY: SecretStr = Field(default="test-deepseek-key")
    OPENAI_API_KEY: SecretStr = Field(default="test-openai-key")
    LLM_PROVIDER: str = Field(default="deepseek", description="Default LLM provider to use (deepseek, openai)")
    LLM_MODEL: str = Field(default="deepseek-chat", description="Default DeepSeek model to use")
    LLM_TEMPERATURE: float = Field(default=0.7, description="LLM temperature setting")
    LLM_MAX_TOKENS: int = Field(default=1000, description="Maximum tokens per LLM request")
    OPENAI_FALLBACK_MODEL: str = Field(default="gpt-4o", description="Fallback OpenAI model to use if DeepSeek is unavailable")

    # Social auth settings
    FACEBOOK_APP_TOKEN: str = Field(default="test-facebook-app-token")
    GOOGLE_CLIENT_ID: str = Field(default="test-google-client-id")
    GOOGLE_CLIENT_SECRET: str = Field(default="test-google-client-secret")

    # Email settings
    EMAIL_TEMPLATES_DIR: str = str(_BASE_DIR / "core" / "templates" / "email")
    EMAIL_SUBJECT_PREFIX: str = Field(default="[AI Agentic Deals]")
    EMAIL_SENDER_NAME: str = Field(default="AI Agentic Deals")
    EMAIL_SENDER_ADDRESS: str = Field(default="noreply@aideals.com")
    EMAIL_FROM: str = Field(default="AI Agentic Deals <noreply@aideals.com>")
    EMAIL_BACKEND: str = Field(
        default="core.services.email.backends.console.ConsoleEmailBackend",
        description="Email backend class"
    )
    EMAIL_HOST: str = Field(default="smtp.gmail.com", description="SMTP host")
    EMAIL_PORT: int = Field(default=587, description="SMTP port")
    EMAIL_USE_TLS: bool = Field(default=True, description="Use TLS for email")
    EMAIL_USE_SSL: bool = Field(default=False, description="Use SSL for email")
    EMAIL_USERNAME: Optional[str] = Field(default=None, description="SMTP username")
    EMAIL_PASSWORD: Optional[SecretStr] = Field(default=None, description="SMTP password")
    EMAIL_TIMEOUT: int = Field(default=30, description="Email timeout in seconds")
    EMAIL_RETRY_COUNT: int = Field(default=3, description="Number of times to retry sending email")
    EMAIL_RETRY_DELAY: int = Field(default=1, description="Delay between retries in seconds")

    # Performance settings
    SLOW_REQUEST_THRESHOLD: float = Field(default=1.0)  # seconds
    COMPRESSION_MINIMUM_SIZE: int = Field(default=500)  # bytes

    # Cache settings
    MARKET_CACHE_TTL: int = Field(default=3600)
    PRODUCT_CACHE_TTL: int = Field(default=1800)
    TOKEN_CACHE_TTL: int = Field(default=3000)
    BALANCE_CACHE_TTL: int = Field(default=1800, description="Token balance cache TTL in seconds")
    GOAL_CACHE_TTL: int = Field(default=3600, description="Goal cache TTL in seconds")

    # Celery settings
    CELERY_BROKER_URL: Optional[str] = Field(default=None, description="Celery broker URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, description="Celery result backend")
    CELERY_TASK_SERIALIZER: str = Field(default="json", description="Celery task serializer")
    CELERY_RESULT_SERIALIZER: str = Field(default="json", description="Celery result serializer")
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"], description="Celery accepted content types")
    CELERY_TIMEZONE: str = Field(default="UTC", description="Celery timezone")
    CELERY_TASK_TIME_LIMIT: int = Field(default=30 * 60, description="Task time limit in seconds")
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=25 * 60, description="Task soft time limit in seconds")

    # Agent settings
    AGENT_MEMORY_LIMIT: int = Field(default=512, description="Agent memory limit in MB")
    AGENT_TIMEOUT: int = Field(default=30, description="Agent timeout in seconds")
    AGENT_MAX_RETRIES: int = Field(default=3, description="Maximum agent retry attempts")
    AGENT_BATCH_SIZE: int = Field(default=100, description="Agent batch processing size")
    AGENT_QUEUE_PREFIX: str = Field(default="agent", description="Agent queue prefix")

    # File upload settings
    MAX_UPLOAD_SIZE: int = Field(default=5 * 1024 * 1024, description="Maximum upload size in bytes")
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".pdf"],
        description="Allowed upload file extensions"
    )
    UPLOAD_DIR: str = Field(default="uploads", description="Upload directory path")

    # Monitoring settings
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    PROMETHEUS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics")
    HEALTH_CHECK_ENABLED: bool = Field(default=True, description="Enable health checks")

    # Debug settings
    DEBUG: bool = Field(default=False)

    # Blockchain settings
    SOL_NETWORK_RPC: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana network RPC endpoint"
    )
    SOL_NETWORK: str = Field(
        default="mainnet-beta",
        description="Solana network (mainnet-beta, testnet, devnet)"
    )
    COMMITMENT_LEVEL: str = Field(
        default="confirmed",
        description="Solana commitment level for transactions"
    )

    # Token settings
    TOKEN_CONTRACT_ADDRESS: str = Field(
        default="your_token_program_id",
        description="Token program ID on Solana"
    )
    TOKEN_REQUIRED_BALANCE: float = Field(
        default=10.0,
        description="Minimum token balance required for operations"
    )
    TOKEN_SEARCH_COST: float = Field(
        default=1.0,
        description="Token cost per search operation"
    )
    TOKEN_DECIMALS: int = Field(
        default=9,
        description="Token decimal places"
    )

    # Goal settings
    MAX_GOAL_PRICE: float = Field(
        default=10000.0,
        description="Maximum allowed goal price"
    )
    MAX_GOAL_DEADLINE_DAYS: int = Field(
        default=90,
        description="Maximum allowed deadline in days from now"
    )

    # Security settings
    SSL_REQUIRED: bool = Field(
        default=True,
        description="Require SSL for all connections"
    )

    # Market rate limits
    AMAZON_RATE_LIMIT: int = Field(
        default=50,
        description="Amazon API rate limit per minute"
    )
    WALMART_RATE_LIMIT: int = Field(
        default=50,
        description="Walmart API rate limit per minute"
    )
    EBAY_RATE_LIMIT: int = Field(
        default=50,
        description="eBay API rate limit per minute"
    )

    # Firebase Cloud Messaging settings
    FCM_PROJECT_ID: str = Field(
        default="test-fcm-project",
        description="Firebase Cloud Messaging project ID"
    )
    FCM_API_KEY: SecretStr = Field(
        default="test-fcm-api-key",
        description="Firebase Cloud Messaging API key"
    )
    FCM_PRIVATE_KEY: SecretStr = Field(
        default="test-fcm-key",
        description="Firebase Cloud Messaging private key"
    )
    FCM_CLIENT_EMAIL: str = Field(
        default="test@fcm.com",
        description="Firebase Cloud Messaging client email"
    )
    FCM_ENDPOINT: str = Field(
        default="https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        description="Firebase Cloud Messaging API endpoint"
    )
    FCM_SCOPE: str = Field(
        default="https://www.googleapis.com/auth/firebase.messaging",
        description="Firebase Cloud Messaging API scope"
    )
    FCM_TOKEN_URL: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Firebase Cloud Messaging token URL"
    )
    FCM_AUTH_PROVIDER_URL: str = Field(
        default="https://accounts.google.com/o/oauth2/auth",
        description="Firebase Cloud Messaging auth provider URL"
    )
    FCM_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of FCM send retries"
    )
    FCM_RETRY_DELAY: int = Field(
        default=1,
        description="Delay between FCM retries in seconds"
    )
    FCM_BATCH_SIZE: int = Field(
        default=500,
        description="Maximum number of messages per FCM batch"
    )

    @model_validator(mode='before')
    @classmethod
    def build_database_url(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build database URL from components if not provided."""
        print("DEBUG: Starting database URL validation")
        
        # Check for AWS environment indicators
        is_aws = os.environ.get("AWS_EXECUTION_ENV") is not None or \
                 os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None or \
                 os.environ.get("ECS_CONTAINER_METADATA_URI") is not None
        
        if is_aws:
            print("DEBUG: Running in AWS environment")
        
        # If DATABASE_URL is not already set
        if not values.get("DATABASE_URL"):
            try:
                # Get individual components with defaults
                db_user = values.get("POSTGRES_USER", "postgres")
                db_password = values.get("POSTGRES_PASSWORD", "postgres")
                
                # Prioritize AWS RDS hostname if available
                db_host = values.get("POSTGRES_HOST")
                if not db_host:
                    # Check environment directly in case it's set but not loaded in values yet
                    db_host = os.environ.get("POSTGRES_HOST")
                    if db_host:
                        # Don't log the actual host
                        print("DEBUG: Found POSTGRES_HOST in environment")
                        values["POSTGRES_HOST"] = db_host
                
                # If still no host, use default
                if not db_host:
                    # Use "localhost" in AWS instead of "deals_postgres" to avoid DNS errors
                    db_host = "localhost" if is_aws else "deals_postgres"
                    print("DEBUG: Using default database host")
                
                db_port = values.get("POSTGRES_PORT", "5432")
                db_name = values.get("POSTGRES_DB", "agentic_deals")
                
                # Print minimal info for debugging (no sensitive details)
                print("DEBUG: Building database URL with default parameters")
                
                # Make sure port is an integer when converted
                try:
                    db_port = str(int(db_port))
                except (ValueError, TypeError):
                    print(f"DEBUG: Invalid port value, using default 5432")
                    db_port = "5432"
                
                # Ensure the password is URL encoded
                import urllib.parse
                
                # Remove any existing URL encoding to prevent double-encoding
                def clean_component(s):
                    """Clean a URL component to prevent double encoding."""
                    try:
                        # First try to decode in case it's already encoded
                        decoded = urllib.parse.unquote(str(s))
                        # Then encode it properly
                        return urllib.parse.quote_plus(decoded)
                    except Exception as e:
                        print(f"DEBUG: Error cleaning URL component")
                        return urllib.parse.quote_plus(str(s))
                
                encoded_user = clean_component(db_user)
                encoded_password = clean_component(db_password)
                encoded_host = db_host  # Don't encode hostname
                
                # Build the database URL string with the correct driver
                # Use asyncpg for normal operation, but psycopg2 for migrations
                if "alembic" in sys.modules:
                    print("DEBUG: Using psycopg2 driver for Alembic migrations")
                    db_driver = "postgresql"
                else:
                    print("DEBUG: Using asyncpg driver for normal operation")
                    db_driver = "postgresql+asyncpg"
                
                values["DATABASE_URL"] = f"{db_driver}://{encoded_user}:{encoded_password}@{encoded_host}:{db_port}/{db_name}"
                print("DEBUG: Database URL successfully built")
                
                # Skip validation as the PostgresDsn class doesn't have a validate method directly
                # This addresses the linter error "Class 'PostgresDsn' has no 'validate' member"
                
            except Exception as e:
                print(f"DEBUG: Error building database URL")
                # Provide a fallback URL
                if is_aws:
                    print("DEBUG: Using fallback database URL for AWS")
                    values["DATABASE_URL"] = f"postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_deals"
                else:
                    print("DEBUG: Using fallback database URL for development")
                    values["DATABASE_URL"] = f"postgresql+asyncpg://postgres:12345678@deals_postgres:5432/agentic_deals"
        
        return values

    @model_validator(mode='before')
    @classmethod
    def build_redis_url(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build Redis URL from components if not provided."""
        print("DEBUG: Starting Redis URL validation")
        
        # Check if we're running in AWS
        is_aws = False
        if values.get("APP_ENVIRONMENT") == "production":
            is_aws = True
            print("DEBUG: Running in production environment")
        
        # Check if REDIS_URL is already provided
        if values.get("REDIS_URL"):
            print("DEBUG: Using pre-configured REDIS_URL")
            
            # Check if the URL contains default passwords and remove them
            redis_url = str(values.get("REDIS_URL"))
            if "your_redis_password" in redis_url or "your_production_redis_password" in redis_url:
                print("DEBUG: Removing default password from REDIS_URL")
                # Parse the URL and remove the password
                from urllib.parse import urlparse, urlunparse
                parsed_url = urlparse(redis_url)
                
                # Extract host and port from netloc
                netloc_parts = parsed_url.netloc.split("@")
                if len(netloc_parts) > 1:
                    # There's an auth part, remove it
                    netloc = netloc_parts[1]
                else:
                    netloc = netloc_parts[0]
                
                # Reconstruct URL without password
                values["REDIS_URL"] = urlunparse((
                    parsed_url.scheme,
                    netloc,
                    parsed_url.path,
                    parsed_url.params,
                    parsed_url.query,
                    parsed_url.fragment
                ))
                print("DEBUG: Modified REDIS_URL to remove default password")
            
            # Force redis host to be set from URL to avoid confusion
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(values["REDIS_URL"])
                
                # Extract host from netloc
                netloc_parts = parsed_url.netloc.split("@")
                if len(netloc_parts) > 1:
                    # There's an auth part
                    host_port = netloc_parts[1].split(":")
                else:
                    host_port = netloc_parts[0].split(":")
                
                # Set REDIS_HOST
                values["REDIS_HOST"] = host_port[0]
                print("DEBUG: Extracted REDIS_HOST from URL")
                
                # Set REDIS_PORT if present
                if len(host_port) > 1:
                    try:
                        values["REDIS_PORT"] = int(host_port[1].split("/")[0])
                        print("DEBUG: Extracted REDIS_PORT from URL")
                    except (ValueError, IndexError):
                        pass
                
                # Set REDIS_DB if present
                if "/" in values["REDIS_URL"]:
                    try:
                        db_part = values["REDIS_URL"].split("/")[-1]
                        values["REDIS_DB"] = int(db_part)
                        print("DEBUG: Extracted REDIS_DB from URL")
                    except (ValueError, IndexError):
                        pass
                
            except Exception as e:
                print("DEBUG: Error parsing Redis URL components")
            
            return values
            
        if not values.get("REDIS_URL"):
            try:
                # Prioritize Redis host from environment variables
                redis_host = values.get("REDIS_HOST")
                if not redis_host:
                    # Check environment directly in case it's set but not loaded in values yet
                    redis_host = os.environ.get("REDIS_HOST")
                    if redis_host:
                        print("DEBUG: Found REDIS_HOST in environment")
                        values["REDIS_HOST"] = redis_host
                
                # If still no host, use default
                if not redis_host:
                    # Use "localhost" in AWS instead of "deals_redis" to avoid DNS errors
                    redis_host = "localhost" if is_aws else "redis"
                    print("DEBUG: Using default Redis host")
                
                # Ensure port is an integer
                try:
                    redis_port = int(values.get("REDIS_PORT", 6379))
                except (ValueError, TypeError):
                    print("DEBUG: Invalid Redis port value, using default 6379")
                    redis_port = 6379
                
                # Ensure DB is an integer
                try:
                    redis_db = int(values.get("REDIS_DB", 0))
                except (ValueError, TypeError):
                    print("DEBUG: Invalid Redis DB value, using default 0")
                    redis_db = 0
                
                # Get password from environment or settings
                redis_password = values.get("REDIS_PASSWORD", "")
                if not redis_password:
                    redis_password = os.environ.get("REDIS_PASSWORD", "")
                    if redis_password:
                        print("DEBUG: Using Redis password from environment")
                        values["REDIS_PASSWORD"] = redis_password
                
                # Check if password is a default value and skip it
                if redis_password in ["your_redis_password", "your_production_redis_password"]:
                    print("DEBUG: Ignoring default Redis password")
                    redis_password = ""
                
                print("DEBUG: Building Redis URL with configured parameters")
                
                # Store the components for later use
                values["REDIS_HOST"] = redis_host
                values["REDIS_PORT"] = redis_port
                values["REDIS_DB"] = redis_db
                
                # Build Redis URL based on whether password is provided
                if redis_password and redis_password not in ["your_redis_password", "your_production_redis_password"]:
                    # Simple URL construction without URL encoding to avoid issues
                    values["REDIS_URL"] = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
                else:
                    values["REDIS_URL"] = f"redis://{redis_host}:{redis_port}/{redis_db}"
                
                print("DEBUG: Redis URL successfully built")
                
            except Exception as e:
                print("DEBUG: Error building Redis URL")
                # Provide a fallback URL for development
                if is_aws:
                    print("DEBUG: Using fallback Redis URL for AWS")
                    values["REDIS_URL"] = "redis://localhost:6379/0"
                else:
                    print("DEBUG: Using fallback Redis URL for development")
                    values["REDIS_URL"] = "redis://redis:6379/0"
                
        return values

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL."""
        return str(self.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get SQLAlchemy database URI."""
        return str(self.DATABASE_URL)

    @computed_field
    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL."""
        return self.CELERY_BROKER_URL or str(self.REDIS_URL)

    @computed_field
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL."""
        return self.CELERY_RESULT_BACKEND or str(self.REDIS_URL)

    @model_validator(mode='before')
    @classmethod
    def set_host_and_hosts(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Set host and hosts fields from environment variables."""
        # Ensure we have at least one of host or hosts
        if 'host' not in values and 'hosts' not in values:
            # If neither is set, use default hosts
            values['hosts'] = ["localhost"]
            values['host'] = "localhost"
        
        # If only host is set but not hosts
        if 'host' in values and 'hosts' not in values:
            # Convert host to hosts list format
            values['hosts'] = [values['host']]
        
        # If only hosts is set but not host
        if 'hosts' in values and 'host' not in values:
            # Use first host as the default host
            values['host'] = values['hosts'][0] if values['hosts'] else "localhost"
        
        # Make sure both are valid values
        if not values.get('host'):
            values['host'] = "localhost"
            
        if not values.get('hosts'):
            values['hosts'] = ["localhost"]
        
        return values

    class Config:
        """Pydantic model configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

        # Update settings for test environment
        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ):
            # First get values from normal sources
            from pydantic.v1.env_settings import SettingsSourceCallable
            from functools import partial
            
            # Chain the settings sources
            result = (init_settings, env_settings, file_secret_settings)

            # Then apply test-specific overrides
            def test_override(settings_dict):
                if settings_dict.get("TESTING", False):
                    # Use shorter token expiration for tests
                    settings_dict["ACCESS_TOKEN_EXPIRE_MINUTES"] = 5
                    settings_dict["REFRESH_TOKEN_EXPIRE_DAYS"] = 1

                    # Skip token verification in tests
                    settings_dict["SKIP_TOKEN_VERIFICATION"] = True

                    # Use in-memory SQLite for tests if not explicitly set
                    if "DATABASE_URL" in settings_dict and settings_dict["DATABASE_URL"] and "sqlite" not in str(settings_dict["DATABASE_URL"]).lower() and os.environ.get("TEST_DATABASE_URL") is None:
                        settings_dict["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

                    # Use mock Redis for tests if not explicitly set
                    if "REDIS_URL" in settings_dict and settings_dict["REDIS_URL"] and os.environ.get("TEST_REDIS_URL") is None:
                        settings_dict["REDIS_HOST"] = "localhost"
                        settings_dict["REDIS_PORT"] = 6379
                        settings_dict["REDIS_DB"] = 1  # Use different DB for tests
                        settings_dict["REDIS_URL"] = f"redis://{settings_dict['REDIS_HOST']}:{settings_dict['REDIS_PORT']}/{settings_dict['REDIS_DB']}"
                return settings_dict

            # Create a callable that properly chains the sources and applies our override
            def combined_sources():
                # First apply the normal sources in sequence
                settings_dict = {}
                for source in result:
                    settings_dict.update(source())
                # Then apply our test overrides
                return test_override(settings_dict)
                
            return combined_sources 
