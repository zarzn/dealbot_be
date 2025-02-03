"""Development configuration for the AI Agentic Deals System."""

from core.config.base import BaseConfig

class DevelopmentConfig(BaseConfig):
    # Application
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = "your-secret-key-for-development"
    JWT_SECRET: str = "your-jwt-secret-for-development"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
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
    REDIS_HOST: str = "redis"
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
    MARKET_CACHE_TTL: int = 1800
    PRODUCT_CACHE_TTL: int = 900
    TOKEN_CACHE_TTL: int = 1500
    
    # AI Services
    DEEPSEEK_API_KEY: str = "your-deepseek-api-key"
    OPENAI_API_KEY: str = "your-openai-api-key"
    
    # Token System
    ETH_NETWORK_RPC: str = "https://api.devnet.solana.com"
    SOL_NETWORK_RPC: str = "https://api.devnet.solana.com"
    SOL_NETWORK: str = "devnet"
    TOKEN_CONTRACT_ADDRESS: str = "your_token_program_id"
    TOKEN_REQUIRED_BALANCE: float = 1.0
    TOKEN_SEARCH_COST: float = 0.1
    
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
    RATE_LIMIT_PER_SECOND: int = 20
    RATE_LIMIT_PER_MINUTE: int = 300
    
    class Config:
        case_sensitive = True 