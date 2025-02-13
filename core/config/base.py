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
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: SecretStr
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    DB_IDLE_TIMEOUT: int = 300
    DB_MAX_OVERFLOW: int = 10
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: int = 1

    @model_validator(mode='before')
    @classmethod
    def assemble_db_url(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble database URL with the correct format for asyncpg."""
        if isinstance(data.get("DATABASE_URL"), str):
            return data
        
        port = data.get("POSTGRES_PORT")
        if isinstance(port, str):
            port = int(port)
        
        # Construct URL as a string
        data["DATABASE_URL"] = f"postgresql+asyncpg://{data.get('POSTGRES_USER')}:{data.get('POSTGRES_PASSWORD')}@{data.get('POSTGRES_HOST')}:{port}/{data.get('POSTGRES_DB')}"
        return data

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_SIZE: int = 10
    REDIS_TIMEOUT: int = 5
    REDIS_URL: Optional[RedisDsn] = None
    REDIS_SSL: bool = False

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
    DEEPSEEK_API_KEY: str
    OPENAI_API_KEY: Optional[str] = None
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

    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]

    # Rate Limiting
    RATE_LIMIT_PER_SECOND: int = 10
    RATE_LIMIT_PER_MINUTE: int = 200

    model_config = {
        "case_sensitive": True,
        "env_file": os.path.join(BACKEND_DIR, ".env.development"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }