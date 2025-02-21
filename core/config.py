"""Application configuration module.

This module defines all configuration settings for the AI Agentic Deals System,
including database, cache, security, and external service configurations.
"""

from typing import Dict, Any, Optional, List, Union, Set
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path
from pydantic import PostgresDsn, RedisDsn, SecretStr, HttpUrl, EmailStr, conint, confloat
from . import constants

try:
    BACKEND_DIR = Path(__file__).resolve().parent.parent
except Exception:
    BACKEND_DIR = Path(os.getcwd()) / 'backend'

class Settings(BaseSettings):
    """Application settings"""
    # Application
    APP_NAME: str = "AI Agentic Deals System"
    APP_VERSION: str = constants.API_VERSION
    APP_DESCRIPTION: str = "AI-powered deal monitoring system"
    APP_ENV: str = "development"
    DEBUG: bool = False
    TESTING: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: SecretStr = SecretStr("your-secret-key-here")  # Default for development
    API_PREFIX: str = constants.API_PREFIX
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: List[str] = ["*"]

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_DB: str = "deals"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: conint(ge=1, le=65535) = 5432
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = constants.DB_POOL_SIZE
    DB_MAX_OVERFLOW: int = constants.DB_MAX_OVERFLOW
    DB_POOL_TIMEOUT: int = constants.DB_POOL_TIMEOUT
    DB_POOL_RECYCLE: int = constants.DB_POOL_RECYCLE
    DB_MAX_RETRIES: conint(ge=1) = 3
    DB_RETRY_DELAY: confloat(ge=0.1) = 1.0
    DB_STATEMENT_TIMEOUT: conint(ge=1) = 30  # seconds
    DB_IDLE_TIMEOUT: conint(ge=1) = 300  # 5 minutes

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get database URL with proper credentials escaping"""
        # In test environment, always build from components
        if self.TESTING or self.ENVIRONMENT == "development":
            try:
                return str(
                    PostgresDsn.build(
                        scheme="postgresql+asyncpg",
                        username=self.POSTGRES_USER,
                        password=self.POSTGRES_PASSWORD.get_secret_value(),
                        host=self.POSTGRES_HOST,
                        port=self.POSTGRES_PORT,
                        path=self.POSTGRES_DB
                    )
                )
            except Exception as e:
                raise ValueError(f"Invalid database configuration: {str(e)}")
        
        # For other environments, try DATABASE_URL first
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        
        # Fall back to building from components
        try:
            return str(
                PostgresDsn.build(
                    scheme="postgresql+asyncpg",
                    username=self.POSTGRES_USER,
                    password=self.POSTGRES_PASSWORD.get_secret_value(),
                    host=self.POSTGRES_HOST,
                    port=self.POSTGRES_PORT,
                    path=self.POSTGRES_DB
                )
            )
        except Exception as e:
            raise ValueError(f"Invalid database configuration: {str(e)}")

    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL with proper credentials escaping"""
        if self.DATABASE_URL:
            # Replace asyncpg with psycopg2 for sync operations
            return str(self.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")
        
        try:
            return str(
                PostgresDsn.build(
                    scheme="postgresql",
                    username=self.POSTGRES_USER,
                    password=self.POSTGRES_PASSWORD.get_secret_value(),
                    host=self.POSTGRES_HOST,
                    port=self.POSTGRES_PORT,
                    path=self.POSTGRES_DB  # Always use main database
                )
            )
        except Exception as e:
            raise ValueError(f"Invalid database configuration: {str(e)}")

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: conint(ge=1, le=65535) = 6379
    REDIS_DB: conint(ge=0) = 0
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_SSL: bool = False
    REDIS_POOL_SIZE: int = 10
    REDIS_TIMEOUT: int = 10
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_URL: Optional[str] = None
    REDIS_MAX_RETRIES: conint(ge=1) = 3
    REDIS_RETRY_DELAY: confloat(ge=0.1) = 1.0
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_KEY_PREFIX: str = "deals:"
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 10
    REDIS_SOCKET_READ_TIMEOUT: int = 10
    REDIS_SOCKET_WRITE_TIMEOUT: int = 10
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    REDIS_MAX_CONNECTION_CALLS: int = 0  # Unlimited

    @property
    def redis_url(self) -> str:
        """Get Redis URL with proper credentials escaping"""
        if self.REDIS_URL:
            return str(self.REDIS_URL)
        
        try:
            auth = f":{self.REDIS_PASSWORD.get_secret_value()}@" if self.REDIS_PASSWORD else ""
            scheme = "rediss" if self.REDIS_SSL else "redis"
            return f"{scheme}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        except Exception as e:
            logger.error(f"Failed to build Redis URL: {str(e)}")
            return "redis://localhost:6379/0"

    # Token System
    SOL_NETWORK_RPC: HttpUrl = HttpUrl("https://api.mainnet-beta.solana.com")  # Default mainnet
    SOL_NETWORK: str = "mainnet-beta"
    TOKEN_CONTRACT_ADDRESS: str = ""  # Must be set in environment
    TOKEN_REQUIRED_BALANCE: confloat(ge=0) = 10.0
    TOKEN_SEARCH_COST: confloat(ge=0) = 1.0
    TOKEN_DECIMALS: conint(ge=0, le=9) = 9
    COMMITMENT_LEVEL: str = "confirmed"
    
    # Network settings
    MAX_RETRIES: conint(ge=1) = 3
    RETRY_DELAY: confloat(ge=0.1) = 1.0
    REQUEST_TIMEOUT: confloat(ge=1) = 30.0
    WEBSOCKET_TIMEOUT: confloat(ge=1) = 60.0

    # Market APIs
    AMAZON_ACCESS_KEY: Optional[SecretStr] = None
    AMAZON_SECRET_KEY: Optional[SecretStr] = None
    AMAZON_PARTNER_TAG: str = ""
    AMAZON_COUNTRY: str = "US"

    WALMART_CLIENT_ID: Optional[SecretStr] = None
    WALMART_CLIENT_SECRET: Optional[SecretStr] = None

    # ScraperAPI Configuration
    SCRAPER_API_KEY: SecretStr = SecretStr("34b092724b61ff18f116305a51ee77e7")
    SCRAPER_API_BASE_URL: str = "http://api.scraperapi.com"
    SCRAPER_API_CONCURRENT_LIMIT: conint(ge=1) = 25
    SCRAPER_API_REQUESTS_PER_SECOND: conint(ge=1) = 3
    SCRAPER_API_MONTHLY_LIMIT: conint(ge=1) = 200_000
    SCRAPER_API_TIMEOUT: conint(ge=1) = 70
    SCRAPER_API_CACHE_TTL: conint(ge=1) = 1800  # 30 minutes
    SCRAPER_API_BACKGROUND_CACHE_TTL: conint(ge=1) = 7200  # 2 hours

    # AI Services
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None

    # Rate Limiting
    RATE_LIMIT_PER_SECOND: conint(ge=1) = 5
    RATE_LIMIT_PER_MINUTE: conint(ge=1) = 100
    RATE_LIMIT_BURST_MULTIPLIER: confloat(ge=1) = 2.0

    # Market Rate Limiting
    MARKET_DEFAULT_RATE_LIMIT: conint(ge=1) = 50
    AMAZON_RATE_LIMIT: conint(ge=1) = 50
    WALMART_RATE_LIMIT: conint(ge=1) = 50
    EBAY_RATE_LIMIT: conint(ge=1) = 50

    # Cache TTLs (in seconds)
    MARKET_CACHE_TTL: conint(ge=1) = 3600
    PRODUCT_CACHE_TTL: conint(ge=1) = 1800
    TOKEN_CACHE_TTL: conint(ge=1) = 3000
    USER_CACHE_TTL: conint(ge=1) = 300
    SESSION_CACHE_TTL: conint(ge=1) = 1800

    # Monitoring
    SENTRY_DSN: Optional[HttpUrl] = None
    PROMETHEUS_ENABLED: bool = True
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_RETENTION_DAYS: conint(ge=1) = 30

    # Security
    SSL_REQUIRED: bool = True
    CORS_ORIGINS: List[Union[str, HttpUrl]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1",
        "https://deals.yourdomain.com",
        "https://api.deals.yourdomain.com"
    ]
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
    JWT_ALGORITHM: str = constants.JWT_ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: conint(ge=1) = constants.ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: conint(ge=1) = constants.REFRESH_TOKEN_EXPIRE_DAYS
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: conint(ge=1) = 24
    MIN_PASSWORD_LENGTH: conint(ge=8) = constants.PASSWORD_MIN_LENGTH
    REQUIRE_PASSWORD_CONFIRMATION: bool = True
    MAX_LOGIN_ATTEMPTS: conint(ge=1) = constants.MAX_LOGIN_ATTEMPTS
    LOGIN_ATTEMPT_TIMEOUT: conint(ge=1) = constants.LOCKOUT_DURATION_MINUTES * 60
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SENSITIVE_HEADERS: Set[str] = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-csrf-token",
        "x-xsrf-token",
        "x-forwarded-for",
        "x-real-ip",
        "proxy-authorization",
        "www-authenticate",
        "proxy-authenticate"
    }
    SENSITIVE_FIELDS: Set[str] = {
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

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_REQUEST_BODY: bool = True
    LOG_RESPONSE_BODY: bool = False
    LOGGING_EXCLUDE_PATHS: Set[str] = {
        "/api/v1/health",
        "/api/v1/metrics",
        "/docs",
        "/redoc",
        "/openapi.json"
    }
    LOG_FILE: Optional[Path] = None
    LOG_RETENTION_DAYS: conint(ge=1) = 30
    LOG_MAX_SIZE: conint(ge=1) = 10485760  # 10MB

    # Performance
    WORKER_CONNECTIONS: conint(ge=1) = 1000
    KEEPALIVE_TIMEOUT: conint(ge=1) = 65
    GRACEFUL_TIMEOUT: conint(ge=1) = 120

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    CELERY_TASK_SOFT_TIME_LIMIT: conint(ge=1) = 300
    CELERY_TASK_TIME_LIMIT: conint(ge=1) = 600

    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL"""
        return self.CELERY_BROKER_URL or self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL"""
        return self.CELERY_RESULT_BACKEND or self.redis_url

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: conint(ge=1, le=65535) = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_FROM_EMAIL: EmailStr = "noreply@yourdomain.com"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT: conint(ge=1) = 30

    # Notifications
    NOTIFICATION_EMAIL_ENABLED: bool = True
    NOTIFICATION_PUSH_ENABLED: bool = True
    NOTIFICATION_SMS_ENABLED: bool = False
    NOTIFICATION_BATCH_SIZE: conint(ge=1) = 100
    NOTIFICATION_RETRY_ATTEMPTS: conint(ge=1) = 3

    # File Storage
    STORAGE_BACKEND: str = "local"  # local, s3, etc.
    STORAGE_ROOT: Path = Path("storage")
    MAX_UPLOAD_SIZE: conint(ge=1) = 10485760  # 10MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".pdf"]
    IMAGE_THUMBNAIL_SIZES: List[Dict[str, int]] = [
        {"width": 100, "height": 100},
        {"width": 300, "height": 300}
    ]

    # AWS (if using S3)
    AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_ENDPOINT_URL: Optional[HttpUrl] = None
    AWS_USE_SSL: bool = True

    # Email
    EMAIL_SERVER_HOST: str = os.getenv("EMAIL_SERVER_HOST", "smtp.gmail.com")
    EMAIL_SERVER_PORT: int = int(os.getenv("EMAIL_SERVER_PORT", "587"))
    EMAIL_SERVER_USER: str = os.getenv("EMAIL_SERVER_USER", "your-email@gmail.com")
    EMAIL_SERVER_PASSWORD: str = os.getenv("EMAIL_SERVER_PASSWORD", "your-app-specific-password")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "AI Deals <noreply@aiagenticdeals.com>")
    
    # URLs
    SITE_URL: str = os.getenv("SITE_URL", "http://localhost:3000")
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    
    # Token
    SOL_NETWORK_RPC: HttpUrl = HttpUrl("https://api.mainnet-beta.solana.com")
    TOKEN_CONTRACT_ADDRESS: str = os.getenv("TOKEN_CONTRACT_ADDRESS", "")
    TOKEN_REQUIRED_BALANCE: confloat(ge=0) = float(os.getenv("TOKEN_REQUIRED_BALANCE", "0"))
    TOKEN_SEARCH_COST: confloat(ge=0) = float(os.getenv("TOKEN_SEARCH_COST", "1"))
    
    # AI
    OPENAI_API_KEY: Optional[SecretStr] = None
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    
    # AWS
    AWS_ACCESS_KEY: Optional[SecretStr] = None
    AWS_SECRET_KEY: Optional[SecretStr] = None
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    
    # External APIs
    WALMART_API_KEY: Optional[SecretStr] = None
    
    class Config:
        """Pydantic config"""
        env_file = BACKEND_DIR / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None,
            Path: str
        }

    def get_market_rate_limit(self, market: str) -> int:
        """Get rate limit for specific market"""
        return getattr(
            self,
            f"{market.upper()}_RATE_LIMIT",
            self.MARKET_DEFAULT_RATE_LIMIT
        )

    def get_cache_ttl(self, cache_type: str) -> int:
        """Get TTL for specific cache type"""
        return getattr(
            self,
            f"{cache_type.upper()}_CACHE_TTL",
            3600  # Default 1 hour
        )

    def get_db_pool_settings(self) -> Dict[str, Any]:
        """Get database pool settings"""
        return {
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "pool_pre_ping": True
        }

    def get_redis_pool_settings(self) -> Dict[str, Any]:
        """Get Redis pool settings."""
        return {
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_TIMEOUT,
            "socket_keepalive": self.REDIS_SOCKET_KEEPALIVE,
            "retry_on_timeout": True,
            "retry": self.REDIS_MAX_RETRIES,
            "retry_delay": self.REDIS_RETRY_DELAY,
            "health_check_interval": 30,
            "max_connection_calls": 0,  # Unlimited
            "socket_connect_timeout": self.REDIS_TIMEOUT,
            "socket_read_size": 65536,  # 64KB
            "socket_write_timeout": self.REDIS_TIMEOUT
        }

    def get_cors_settings(self) -> Dict[str, Any]:
        """Get CORS settings"""
        return {
            "allow_origins": [str(origin) for origin in self.CORS_ORIGINS],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "max_age": 600  # 10 minutes
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
                },
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": self.LOG_FORMAT,
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": "DEBUG",
                "handlers": ["console"]
            },
            "loggers": {
                "uvicorn": {"level": "DEBUG"},
                "sqlalchemy": {"level": "WARNING"},
                "celery": {"level": "INFO"},
                "fastapi": {"level": "DEBUG"}
            }
        }

        if self.LOG_FILE:
            config["handlers"]["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": self.LOG_FORMAT,
                "filename": self.LOG_FILE,
                "maxBytes": self.LOG_MAX_SIZE,
                "backupCount": self.LOG_RETENTION_DAYS
            }
            config["root"]["handlers"].append("file")

        return config

    def get_celery_config(self) -> Dict[str, Any]:
        """Get Celery configuration"""
        return {
            "broker_url": self.celery_broker_url,
            "result_backend": self.celery_result_backend,
            "task_serializer": self.CELERY_TASK_SERIALIZER,
            "result_serializer": self.CELERY_RESULT_SERIALIZER,
            "accept_content": self.CELERY_ACCEPT_CONTENT,
            "timezone": self.CELERY_TIMEZONE,
            "enable_utc": self.CELERY_ENABLE_UTC,
            "task_soft_time_limit": self.CELERY_TASK_SOFT_TIME_LIMIT,
            "task_time_limit": self.CELERY_TASK_TIME_LIMIT,
            "worker_prefetch_multiplier": 1,
            "worker_max_tasks_per_child": 1000,
            "task_acks_late": True,
            "task_reject_on_worker_lost": True
        }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Create settings instance
settings = get_settings()

# Export settings instance
__all__ = ['settings', 'Settings', 'get_settings']
