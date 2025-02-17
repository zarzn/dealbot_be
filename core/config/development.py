"""Development configuration for the AI Agentic Deals System."""

from .base import BaseConfig
from ..constants import (
    MIN_TOKEN_BALANCE,
    SEARCH_COST,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_AUTHENTICATED,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_ALGORITHM,
    REDIS_MAX_CONNECTIONS,
    REDIS_POOL_SIZE,
    REDIS_TIMEOUT,
    REDIS_KEY_PREFIX
)
from datetime import timedelta
from pydantic import SecretStr, Field, conint
import os
from typing import Any, Dict, Optional
from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings

class DevelopmentConfig(BaseSettings):
    """Development configuration."""

    # Application
    APP_NAME: str = "AI Agentic Deals API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    ALLOWED_HOSTS: list[str] = ["*"]
    
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
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "30 days"
    LOG_COMPRESSION: bool = True
    LOG_JSON_INDENT: int = 2
    LOG_EXCLUDE_PATHS: set[str] = {
        "/api/v1/health",
        "/api/v1/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    }
    
    # Security
    SECRET_KEY: SecretStr = SecretStr("your-development-secret-key")
    JWT_SECRET: SecretStr = SecretStr("your-jwt-secret-for-development")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = REFRESH_TOKEN_EXPIRE_DAYS
    JWT_ALGORITHM: str = JWT_ALGORITHM
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
    
    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "12345678")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "deals")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "deals_postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    DB_ECHO: bool = True
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: float = 1.0
    DB_IDLE_TIMEOUT: int = 300
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "your_redis_password")
    REDIS_POOL_SIZE: int = REDIS_POOL_SIZE
    REDIS_TIMEOUT: int = REDIS_TIMEOUT
    REDIS_SSL: bool = False
    REDIS_MAX_CONNECTIONS: int = REDIS_MAX_CONNECTIONS
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 10
    REDIS_SOCKET_READ_SIZE: int = 65536  # 64KB
    REDIS_SOCKET_WRITE_TIMEOUT: int = 10
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    REDIS_MAX_CONNECTION_CALLS: int = 0  # Unlimited
    
    # Market Integration
    MARKET_DEFAULT_RATE_LIMIT: int = 50
    AMAZON_RATE_LIMIT: int = 50
    WALMART_RATE_LIMIT: int = 50
    EBAY_RATE_LIMIT: int = 50
    
    # Cache Configuration
    MARKET_CACHE_TTL: int = 1800  # 30 minutes
    PRODUCT_CACHE_TTL: int = 900  # 15 minutes
    TOKEN_CACHE_TTL: int = 1500  # 25 minutes
    SEARCH_CACHE_TTL: int = 600  # 10 minutes
    PRICE_HISTORY_CACHE_TTL: int = 86400  # 24 hours
    MARKET_ANALYSIS_CACHE_TTL: int = 3600  # 1 hour
    
    # AI Services
    DEEPSEEK_API_KEY: str = "your-deepseek-api-key"
    OPENAI_API_KEY: str = "your-openai-api-key"
    
    # Firebase Cloud Messaging
    FCM_API_KEY: str = os.getenv("FCM_API_KEY", "your-fcm-api-key")
    FCM_ENDPOINT: str = os.getenv("FCM_ENDPOINT", "https://fcm.googleapis.com/fcm/send")
    FCM_PROJECT_ID: str = os.getenv("FCM_PROJECT_ID", "your-project-id")
    FCM_CREDENTIALS_PATH: str = os.getenv("FCM_CREDENTIALS_PATH", "path/to/firebase-credentials.json")
    FCM_APP_PACKAGE_NAME: str = os.getenv("FCM_APP_PACKAGE_NAME", "com.yourdomain.app")
    FCM_NOTIFICATION_ICON: str = os.getenv("FCM_NOTIFICATION_ICON", "notification_icon")
    FCM_NOTIFICATION_COLOR: str = os.getenv("FCM_NOTIFICATION_COLOR", "#4A90E2")
    FCM_NOTIFICATION_CLICK_ACTION: str = os.getenv("FCM_NOTIFICATION_CLICK_ACTION", "OPEN_APP")
    FCM_NOTIFICATION_CHANNEL_ID: str = os.getenv("FCM_NOTIFICATION_CHANNEL_ID", "deals_notifications")
    FCM_NOTIFICATION_PRIORITY: str = os.getenv("FCM_NOTIFICATION_PRIORITY", "high")
    FCM_NOTIFICATION_TTL: int = int(os.getenv("FCM_NOTIFICATION_TTL", "86400"))  # 24 hours
    FCM_BATCH_SIZE: int = int(os.getenv("FCM_BATCH_SIZE", "500"))
    FCM_RETRY_COUNT: int = int(os.getenv("FCM_RETRY_COUNT", "3"))
    FCM_RETRY_DELAY: int = int(os.getenv("FCM_RETRY_DELAY", "1000"))  # milliseconds
    
    # Token System
    ETH_NETWORK_RPC: str = "https://api.devnet.solana.com"
    SOL_NETWORK_RPC: str = "https://api.devnet.solana.com"
    SOL_NETWORK: str = "devnet"
    TOKEN_CONTRACT_ADDRESS: str = "your_token_program_id"
    TOKEN_REQUIRED_BALANCE: float = MIN_TOKEN_BALANCE
    TOKEN_SEARCH_COST: float = SEARCH_COST
    
    # Market API Credentials
    AMAZON_ACCESS_KEY: str = "your-amazon-access-key"
    AMAZON_SECRET_KEY: str = "your-amazon-secret-key"
    AMAZON_PARTNER_TAG: str = "your-amazon-partner-tag"
    AMAZON_COUNTRY: str = "US"
    
    WALMART_CLIENT_ID: str = "your-walmart-client-id"
    WALMART_CLIENT_SECRET: str = "your-walmart-client-secret"
    
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
    
    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = RATE_LIMIT_DEFAULT // 60
    RATE_LIMIT_PER_MINUTE: int = RATE_LIMIT_AUTHENTICATED
    RATE_LIMIT_SEARCH: int = 60  # Searches per minute
    RATE_LIMIT_MARKET_API: int = 50  # Market API calls per minute
    RATE_LIMIT_ANALYSIS: int = 100  # Analysis operations per minute
    RATE_LIMIT_BURST: int = 5  # Maximum burst size
    RATE_LIMIT_WINDOW: int = 60  # Window size in seconds
    
    # Deal Analysis
    DEAL_SCORE_WEIGHTS: dict = {
        "price_comparison": 0.6,
        "source_reliability": 0.2,
        "price_stability": 0.2
    }
    DEAL_PRICE_TREND_THRESHOLD: float = 10.0  # Percentage change for trend detection
    DEAL_SCORE_MIN_HISTORY: int = 2  # Minimum price history points for scoring
    DEAL_SCORE_MAX_HISTORY: int = 30  # Maximum price history points for scoring
    
    # Email
    EMAIL_SERVER_HOST: str = os.getenv("EMAIL_SERVER_HOST", "localhost")
    EMAIL_SERVER_PORT: int = int(os.getenv("EMAIL_SERVER_PORT", "1025"))
    EMAIL_SERVER_USER: str = os.getenv("EMAIL_SERVER_USER", "")
    EMAIL_SERVER_PASSWORD: str = os.getenv("EMAIL_SERVER_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@example.com")
    EMAIL_TEMPLATES_DIR: str = os.path.join("core", "templates", "email")

    # Performance
    SLOW_REQUEST_THRESHOLD: float = 1.0  # Threshold in seconds for slow request logging
    WORKER_CONNECTIONS: int = 1000
    KEEPALIVE_TIMEOUT: int = 65
    GRACEFUL_TIMEOUT: int = 120

    # ScraperAPI Configuration
    SCRAPER_API_KEY: SecretStr = Field(default=SecretStr(""), env="SCRAPER_API_KEY")
    SCRAPER_API_BASE_URL: str = Field(default="http://api.scraperapi.com", env="SCRAPER_API_BASE_URL")
    SCRAPER_API_CONCURRENT_LIMIT: conint(ge=1) = Field(default=25, env="SCRAPER_API_CONCURRENT_LIMIT")
    SCRAPER_API_REQUESTS_PER_SECOND: conint(ge=1) = Field(default=3, env="SCRAPER_API_REQUESTS_PER_SECOND")
    SCRAPER_API_MONTHLY_LIMIT: conint(ge=1) = Field(default=200_000, env="SCRAPER_API_MONTHLY_LIMIT")
    SCRAPER_API_TIMEOUT: conint(ge=1) = Field(default=70, env="SCRAPER_API_TIMEOUT")
    SCRAPER_API_CACHE_TTL: conint(ge=1) = Field(default=1800, env="SCRAPER_API_CACHE_TTL")
    SCRAPER_API_BACKGROUND_CACHE_TTL: conint(ge=1) = Field(default=7200, env="SCRAPER_API_BACKGROUND_CACHE_TTL")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """Get database URI."""
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=int(self.POSTGRES_PORT),
            path=self.POSTGRES_DB
        )

    @property
    def DATABASE_URL(self) -> PostgresDsn:
        """Alias for SQLALCHEMY_DATABASE_URI for compatibility."""
        return self.SQLALCHEMY_DATABASE_URI

    @property
    def sync_database_url(self) -> PostgresDsn:
        """Get synchronous database URI."""
        return PostgresDsn.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=int(self.POSTGRES_PORT),
            path=self.POSTGRES_DB
        )

    @property
    def REDIS_URL(self) -> RedisDsn:
        """Get Redis URL."""
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            password=self.REDIS_PASSWORD or None
        )

    class Config:
        """Pydantic config."""
        case_sensitive = True

settings = DevelopmentConfig()
