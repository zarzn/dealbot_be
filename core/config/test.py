"""Test configuration module."""

import os
from typing import Any, Dict, Optional

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings

class TestSettings(BaseSettings):
    """Test settings."""

    # Application
    APP_NAME: str = "AI Agentic Deals API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "test"
    ALLOWED_HOSTS: list[str] = ["*"]
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: list[str] = [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ]
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "json"
    LOG_REQUEST_BODY: bool = True
    LOG_RESPONSE_BODY: bool = True
    LOG_HEADERS: bool = True
    LOG_QUERY_PARAMS: bool = True
    LOG_PERFORMANCE: bool = True
    LOG_ERRORS: bool = True
    LOG_SLOW_REQUESTS: bool = True
    LOG_SQL_QUERIES: bool = True
    LOG_FILE_PATH: str = "logs/test.log"
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "7 days"
    LOG_COMPRESSION: bool = True
    LOG_JSON_INDENT: int = 2
    LOG_EXCLUDE_PATHS: set[str] = {
        "/api/v1/health",
        "/api/v1/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    }

    # Performance
    SLOW_REQUEST_THRESHOLD: float = 1.0  # Threshold in seconds for slow request logging
    WORKER_CONNECTIONS: int = 1000
    KEEPALIVE_TIMEOUT: int = 65
    GRACEFUL_TIMEOUT: int = 120
    REQUEST_TIMEOUT: int = 60
    RESPONSE_TIMEOUT: int = 60
    BACKLOG_SIZE: int = 2048
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # Authentication
    AUTH_EXCLUDE_PATHS: set[str] = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/health",
        "/"
    }
    SENSITIVE_HEADERS: set[str] = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-token",
        "x-refresh-token",
        "x-client-secret",
        "x-access-token",
        "x-jwt-token",
        "jwt-token",
        "api-key",
        "client-secret",
        "private-key"
    }
    SENSITIVE_FIELDS: set[str] = {
        "password",
        "password_confirmation",
        "current_password",
        "new_password",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
        "private_key",
        "credit_card",
        "card_number",
        "cvv",
        "ssn",
        "social_security"
    }

    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = 10
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_SEARCH: int = 60  # Searches per minute
    RATE_LIMIT_MARKET_API: int = 50  # Market API calls per minute
    RATE_LIMIT_ANALYSIS: int = 100  # Analysis operations per minute
    RATE_LIMIT_BURST: int = 5  # Maximum burst size
    RATE_LIMIT_WINDOW: int = 60  # Window size in seconds

    # Database
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "deals_test")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "12345678")
    DB_ECHO: bool = True
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: float = 1.0
    DB_IDLE_TIMEOUT: int = 300

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """Get database URI."""
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=int(self.POSTGRES_PORT),
            path=f"/{self.POSTGRES_DB}"
        )
    
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        """Get database URL."""
        return self.SQLALCHEMY_DATABASE_URI
    
    @property
    def TEST_DATABASE_URL(self) -> PostgresDsn:
        """Get test database URL."""
        return self.SQLALCHEMY_DATABASE_URI

    @property
    def sync_database_url(self) -> PostgresDsn:
        """Get synchronous database URL."""
        return PostgresDsn.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=int(self.POSTGRES_PORT),
            path=f"/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_CONNECT_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_MAX_RETRIES: int = 3
    REDIS_RETRY_INTERVAL: int = 1
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    REDIS_ENCODING: str = "utf-8"
    REDIS_DECODE_RESPONSES: bool = True

    @property
    def REDIS_URL(self) -> RedisDsn:
        """Get Redis URL."""
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT
        )

    # Email
    EMAIL_SERVER_HOST: str = os.getenv("EMAIL_SERVER_HOST", "mailhog")
    EMAIL_SERVER_PORT: int = int(os.getenv("EMAIL_SERVER_PORT", "1025"))
    EMAIL_SERVER_USER: str = os.getenv("EMAIL_SERVER_USER", "")
    EMAIL_SERVER_PASSWORD: str = os.getenv("EMAIL_SERVER_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "test@example.com")
    EMAIL_TEMPLATES_DIR: str = "core/templates/email"

    # Security
    SECRET_KEY: SecretStr = SecretStr("test-secret-key")
    JWT_SECRET: SecretStr = SecretStr("test-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # Test User
    TEST_USER_EMAIL: str = "test@example.com"
    TEST_USER_PASSWORD: str = "testpassword123"

    # ScraperAPI Configuration
    SCRAPER_API_KEY: str = os.getenv("SCRAPER_API_KEY", "34b092724b61ff18f116305a51ee77e7")
    SCRAPER_API_BASE_URL: str = "http://api.scraperapi.com"
    SCRAPER_API_CONCURRENT_LIMIT: int = 25
    SCRAPER_API_REQUESTS_PER_SECOND: int = 3
    SCRAPER_API_MONTHLY_LIMIT: int = 200_000
    SCRAPER_API_TIMEOUT: int = 70
    SCRAPER_API_CACHE_TTL: int = 1800
    SCRAPER_API_BACKGROUND_CACHE_TTL: int = 7200

    # Solana Configuration
    SOL_NETWORK_RPC: str = "https://api.devnet.solana.com"
    SOL_NETWORK: str = "devnet"
    TOKEN_CONTRACT_ADDRESS: str = "test_token_program_id"
    TOKEN_REQUIRED_BALANCE: float = 0.0
    TOKEN_SEARCH_COST: float = 0.0

    # Firebase Cloud Messaging
    FCM_API_KEY: str = "test-fcm-api-key"
    FCM_ENDPOINT: str = "https://fcm.googleapis.com/fcm/send"
    FCM_PROJECT_ID: str = "test-project-id"
    FCM_CREDENTIALS_PATH: str = "path/to/test-firebase-credentials.json"
    FCM_APP_PACKAGE_NAME: str = "com.test.app"
    FCM_NOTIFICATION_ICON: str = "notification_icon"
    FCM_NOTIFICATION_COLOR: str = "#4A90E2"
    FCM_NOTIFICATION_CLICK_ACTION: str = "OPEN_APP"
    FCM_NOTIFICATION_CHANNEL_ID: str = "test_notifications"
    FCM_NOTIFICATION_PRIORITY: str = "high"
    FCM_NOTIFICATION_TTL: int = 86400  # 24 hours
    FCM_BATCH_SIZE: int = 500
    FCM_RETRY_COUNT: int = 3
    FCM_RETRY_DELAY: int = 1000  # milliseconds

    class Config:
        """Pydantic config."""
        case_sensitive = True

settings = TestSettings() 