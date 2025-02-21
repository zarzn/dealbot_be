"""Base configuration for the AI Agentic Deals System."""

from typing import Any, Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import model_validator, PostgresDsn, RedisDsn, SecretStr
import os
from pathlib import Path

# Get the backend directory path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class BaseConfig(BaseSettings):
    # Application
    APP_NAME: str = "AI Deals System"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: SecretStr
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "deals"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    DB_IDLE_TIMEOUT: int = 300
    DB_MAX_OVERFLOW: int = 10
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: int = 1

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
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_SIZE: int = 10
    REDIS_TIMEOUT: int = 5
    REDIS_URL: Optional[RedisDsn] = None
    REDIS_SSL: bool = False
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_CONNECT_TIMEOUT: int = 5

    @model_validator(mode='before')
    @classmethod
    def assemble_redis_url(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(data.get("REDIS_URL"), str):
            return data
        
        port = data.get("REDIS_PORT")
        if isinstance(port, str):
            port = int(port)
            
        password_part = f":{data.get('REDIS_PASSWORD')}@" if data.get("REDIS_PASSWORD") else ""
        data["REDIS_URL"] = f"redis://{password_part}{data.get('REDIS_HOST')}:{port}/{data.get('REDIS_DB')}"
        return data

    # Market Integration
    MARKET_DEFAULT_RATE_LIMIT: int = 100
    AMAZON_RATE_LIMIT: int = 100
    WALMART_RATE_LIMIT: int = 100
    EBAY_RATE_LIMIT: int = 100

    # Cache Configuration
    MARKET_CACHE_TTL: int = 3600
    PRODUCT_CACHE_TTL: int = 1800
    TOKEN_CACHE_TTL: int = 3000

    # AI Services
    DEEPSEEK_API_KEY: SecretStr
    OPENAI_API_KEY: SecretStr
    LLM_MODEL: str = "deepseek"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1000

    # Token System
    ETH_NETWORK_RPC: str
    SOL_NETWORK_RPC: str
    SOL_NETWORK: str = "devnet"
    TOKEN_CONTRACT_ADDRESS: str
    TOKEN_REQUIRED_BALANCE: float = 10.0
    TOKEN_SEARCH_COST: float = 1.0

    # Market API Credentials
    AMAZON_ACCESS_KEY: str
    AMAZON_SECRET_KEY: str
    AMAZON_PARTNER_TAG: str
    AMAZON_COUNTRY: str = "US"

    WALMART_CLIENT_ID: str
    WALMART_CLIENT_SECRET: str

    EBAY_APP_ID: Optional[str] = None
    EBAY_CERT_ID: Optional[str] = None
    EBAY_DEV_ID: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"  # Allow all origins in development
    ]
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_HEADERS: list[str] = [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers"
    ]
    CORS_EXPOSE_HEADERS: list[str] = ["*"]
    CORS_MAX_AGE: int = 600  # 10 minutes
    CORS_ALLOW_CREDENTIALS: bool = True

    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = 10
    RATE_LIMIT_PER_MINUTE: int = 200

    model_config = {
        "case_sensitive": True,
        "env_file": os.path.join(BACKEND_DIR, ".env.development"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }