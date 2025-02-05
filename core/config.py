"""Application configuration module.

This module defines all configuration settings for the AI Agentic Deals System,
including database, cache, security, and external service configurations.
"""

from typing import Dict, Any, Optional, List, Union
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
    ALLOWED_HOSTS: List[str] = ["*"]

    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = SecretStr("postgres")
    POSTGRES_DB: str = "deals"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: conint(ge=1, le=65535) = 5432
    DATABASE_URL: Optional[PostgresDsn] = None
    DB_POOL_SIZE: conint(ge=1) = constants.DB_POOL_SIZE
    DB_MAX_OVERFLOW: conint(ge=1) = constants.DB_MAX_OVERFLOW
    DB_POOL_TIMEOUT: conint(ge=1) = constants.DB_POOL_TIMEOUT
    DB_POOL_RECYCLE: conint(ge=1) = constants.DB_POOL_RECYCLE
    DB_MAX_RETRIES: conint(ge=1) = 3
    DB_RETRY_DELAY: confloat(ge=0.1) = 1.0
    DB_STATEMENT_TIMEOUT: conint(ge=1) = 30  # seconds
    DB_IDLE_TIMEOUT: conint(ge=1) = 300  # 5 minutes

    @property
    def database_url(self) -> str:
        """Get database URL with proper credentials escaping"""
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        
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

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: conint(ge=1, le=65535) = 6379
    REDIS_DB: conint(ge=0) = 0
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_SSL: bool = False
    REDIS_POOL_SIZE: conint(ge=1) = 20
    REDIS_TIMEOUT: conint(ge=1) = 3
    REDIS_URL: Optional[RedisDsn] = None
    REDIS_MAX_RETRIES: conint(ge=1) = 3
    REDIS_RETRY_DELAY: confloat(ge=0.1) = 1.0
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_KEY_PREFIX: str = constants.REDIS_KEY_PREFIX
    REDIS_MAX_CONNECTIONS: conint(ge=1) = constants.REDIS_MAX_CONNECTIONS

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
            raise ValueError(f"Invalid Redis configuration: {str(e)}")

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
    CORS_ORIGINS: List[HttpUrl] = [
        "https://deals.yourdomain.com",
        "https://api.deals.yourdomain.com"
    ]
    JWT_ALGORITHM: str = constants.JWT_ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: conint(ge=1) = constants.ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: conint(ge=1) = constants.REFRESH_TOKEN_EXPIRE_DAYS
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: conint(ge=1) = 24
    MIN_PASSWORD_LENGTH: conint(ge=8) = constants.PASSWORD_MIN_LENGTH
    REQUIRE_PASSWORD_CONFIRMATION: bool = True
    MAX_LOGIN_ATTEMPTS: conint(ge=1) = constants.MAX_LOGIN_ATTEMPTS
    LOGIN_ATTEMPT_TIMEOUT: conint(ge=1) = constants.LOCKOUT_DURATION_MINUTES * 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
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
        """Get Redis pool settings"""
        return {
            "pool_size": self.REDIS_POOL_SIZE,
            "socket_timeout": self.REDIS_TIMEOUT,
            "socket_connect_timeout": self.REDIS_TIMEOUT,
            "socket_keepalive": self.REDIS_SOCKET_KEEPALIVE,
            "retry_on_timeout": True,
            "max_connections": self.REDIS_POOL_SIZE + 10
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
                "level": self.LOG_LEVEL,
                "handlers": ["console"]
            },
            "loggers": {
                "uvicorn": {"level": "INFO"},
                "sqlalchemy": {"level": "WARNING"},
                "celery": {"level": "INFO"}
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
