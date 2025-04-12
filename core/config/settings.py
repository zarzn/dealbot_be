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
    APP_NAME: str = Field(default="RebatOn", description="Application name")
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
    REDIS_HOST: str = Field(default="redis")
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
    API_TITLE: str = Field(default="RebatOn API")
    API_DESCRIPTION: str = Field(default="AI-powered deal monitoring system")
    API_DOCS_URL: str = Field(default="/docs")
    API_REDOC_URL: str = Field(default="/redoc")
    API_OPENAPI_URL: str = Field(default="/openapi.json")
    API_ROOT_PATH: str = Field(default="")
    API_DEBUG: bool = Field(default=False)

    # Site settings
    SITE_URL: str = Field(
        default="http://localhost:3000", 
        description="Frontend site URL, overridden by environment variable in production"
    )

    # Security settings
    SECRET_KEY: SecretStr = Field(default="test-secret-key")
    CORS_ORIGINS: List[str] = Field(default=["https://rebaton.ai", "https://d3irpl0o2ddv9y.cloudfront.net", "http://localhost:3000"])
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
            # Auth endpoints
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/magic-link",
            "/api/v1/auth/social",
            
            # API docs
            "/api/v1/docs",
            "/api/v1/openapi.json",
            
            # System endpoints
            "/api/v1/health",
            "/api/v1/metrics",
            
            # Public endpoints
            "/api/v1/deals/public",
            "/api/v1/deals/open-public",
            "/api/v1/deals/share/auth-debug",
            "/api/v1/deals/share/no-auth-test",
            
            # Contact form endpoint
            "/api/v1/contact",
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
    EMAIL_SUBJECT_PREFIX: str = Field(default="[RebatOn]")
    EMAIL_SENDER_NAME: str = Field(default="RebatOn")
    EMAIL_SENDER_ADDRESS: str = Field(default="noreply@rebaton.ai")
    EMAIL_FROM: str = Field(default="RebatOn <noreply@rebaton.ai>")
    CONTACT_EMAIL: str = Field(default="contact@rebaton.ai")
    ADMIN_EMAIL: str = Field(default="admin@rebaton.ai")
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
    
    # AWS SES Email Settings
    AWS_SES_REGION: str = Field(default="us-east-1", description="AWS SES region")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS access key ID for SES")
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = Field(default=None, description="AWS secret access key for SES")
    AWS_SESSION_TOKEN: Optional[SecretStr] = Field(default=None, description="AWS session token for SES (if using temporary credentials)")
    AWS_SES_SOURCE_ARN: Optional[str] = Field(default=None, description="ARN of the identity to use for sending (optional)")
    AWS_SES_CONFIGURATION_SET: Optional[str] = Field(default=None, description="SES configuration set name (optional)")

    # Oxylabs Settings
    OXYLABS_USERNAME: str = Field(default="", description="Oxylabs API username")
    OXYLABS_PASSWORD: SecretStr = Field(default="", description="Oxylabs API password")
    OXYLABS_BASE_URL: str = Field(default="https://realtime.oxylabs.io", description="Oxylabs API base URL")
    OXYLABS_CONCURRENT_LIMIT: int = Field(default=15, description="Maximum concurrent Oxylabs requests")
    OXYLABS_REQUESTS_PER_SECOND: int = Field(default=5, description="Oxylabs requests per second limit")
    OXYLABS_MONTHLY_LIMIT: int = Field(default=100000, description="Oxylabs monthly request limit")

    # Scraper Configuration
    SCRAPER_TYPE: str = Field(default="oxylabs", description="Default scraper type to use (scraper_api, oxylabs)")

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

    # Stripe Payment Settings
    STRIPE_SECRET_KEY: SecretStr = Field(
        default="sk_test_example",
        description="Stripe secret API key"
    )
    STRIPE_PUBLISHABLE_KEY: str = Field(
        default="pk_test_example",
        description="Stripe publishable API key"
    )
    STRIPE_WEBHOOK_SECRET: SecretStr = Field(
        default="whsec_example",
        description="Stripe webhook secret for signature verification"
    )
    STRIPE_API_VERSION: str = Field(
        default="2023-10-16",
        description="Stripe API version"
    )
    STRIPE_PAYMENT_METHODS: List[str] = Field(
        default=["card"],
        description="Supported Stripe payment methods"
    )
    STRIPE_CURRENCY: str = Field(
        default="usd",
        description="Default currency for Stripe payments"
    )
    STRIPE_PAYMENT_SUCCESS_URL: Optional[str] = Field(
        default=None,
        description="URL to redirect after successful payment"
    )
    STRIPE_PAYMENT_CANCEL_URL: Optional[str] = Field(
        default=None,
        description="URL to redirect after cancelled payment"
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
        if values.get("REDIS_URL") is None:
            # Define a function to clean URL components
            def clean_component(s):
                """Clean special characters from URL components."""
                if not s:
                    return ""
                import urllib.parse
                return urllib.parse.quote(str(s), safe='')
                
            # Get components
            redis_host = values.get("REDIS_HOST", "localhost")
            redis_port = values.get("REDIS_PORT", 6379)
            redis_db = values.get("REDIS_DB", 0)
            redis_password = values.get("REDIS_PASSWORD")
            
            # Build password part of URL if provided
            password_part = ""
            if redis_password:
                if isinstance(redis_password, str):
                    # Clean special characters from password for URL
                    password = clean_component(redis_password)
                    password_part = f":{password}@"
                    # For "your_redis_password", keep it as is (used in Docker)
                    if redis_password == "your_redis_password":
                        password_part = f":{redis_password}@"
                else:
                    # Handle other types (like SecretStr)
                    try:
                        if hasattr(redis_password, "get_secret_value"):
                            password = clean_component(redis_password.get_secret_value())
                            password_part = f":{password}@"
                    except Exception as e:
                        logger.warning(f"Error handling Redis password: {e}")
            
            # Make sure port is a string
            redis_port = str(redis_port)
            
            # Build the Redis URL
            redis_url = f"redis://{password_part}{redis_host}:{redis_port}/{redis_db}"
            values["REDIS_URL"] = redis_url
            
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

    @model_validator(mode='after')
    def set_environment_specific_values(self) -> 'Settings':
        """Set environment-specific values after validation."""
        # Set environment-specific CORS settings
        app_env = self.APP_ENVIRONMENT
        if isinstance(app_env, str) and app_env.lower() == "development":
            # In development, use wildcard for CORS
            self.CORS_ORIGINS = ["*"]
        
        return self

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
                        # Use "redis" as host in Docker environment (default to "redis" which is the Docker service name)
                        settings_dict["REDIS_HOST"] = "redis"
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
