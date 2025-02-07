"""Development configuration for the AI Agentic Deals System."""

from .base import BaseConfig
from ..constants import (
    MIN_TOKEN_BALANCE,
    SEARCH_COST,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_AUTHENTICATED,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_ALGORITHM
)
from datetime import timedelta
from pydantic import SecretStr

class DevelopmentConfig(BaseConfig):
    # Application
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: SecretStr = SecretStr("your-development-secret-key")
    JWT_SECRET: SecretStr = SecretStr("your-jwt-secret-for-development")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = REFRESH_TOKEN_EXPIRE_DAYS
    JWT_ALGORITHM: str = JWT_ALGORITHM
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "deals"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DB_ECHO: bool = True
    DB_POOL_SIZE: int = 5
    DB_POOL_OVERFLOW: int = 10
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = "your_redis_password"
    REDIS_POOL_SIZE: int = 5
    REDIS_TIMEOUT: int = 10
    REDIS_SSL: bool = False
    
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
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "json"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]
    
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
    
    class Config:
        case_sensitive = True
