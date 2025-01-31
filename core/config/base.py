from typing import Any, Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import validator, PostgresDsn, RedisDsn

class BaseConfig(BaseSettings):
    # Application
    PROJECT_NAME: str = "AI Agentic Deals System"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[PostgresDsn] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_url(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_HOST"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB')}"
        )

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    REDIS_POOL_SIZE: int = 10
    REDIS_TIMEOUT: int = 5
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_url(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get("REDIS_PASSWORD") else ""
        return f"redis://{password_part}{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/{values.get('REDIS_DB')}"

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

    # Token System
    ETH_NETWORK_RPC: str
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

    class Config:
        case_sensitive = True 