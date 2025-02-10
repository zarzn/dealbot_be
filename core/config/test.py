"""Test configuration module."""

import os
from typing import Any, Dict, Optional

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings

class TestSettings(BaseSettings):
    """Test settings."""

    # Database
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db-test")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "deals_test")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "test_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "test_password")

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

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis-test")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

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
    JWT_SECRET: str = os.getenv("JWT_SECRET", "test_secret")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Test User
    TEST_USER_EMAIL: str = "test@example.com"
    TEST_USER_PASSWORD: str = "testpassword123"

    class Config:
        """Pydantic config."""
        case_sensitive = True

settings = TestSettings() 