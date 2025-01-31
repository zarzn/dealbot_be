from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    # Application
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database - Default local setup
    POSTGRES_HOST: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "deals"
    
    # Redis - Default local setup
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "your_redis_password"
    REDIS_SSL: bool = False
    
    # CORS - Allow all in development
    CORS_ORIGINS: list[str] = ["*"]
    
    # Rate Limiting - More permissive in development
    RATE_LIMIT_PER_SECOND: int = 30
    RATE_LIMIT_PER_MINUTE: int = 500
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "text"  # More readable format for development
    
    # Market Rate Limits - More permissive for development
    MARKET_DEFAULT_RATE_LIMIT: int = 200
    AMAZON_RATE_LIMIT: int = 200
    WALMART_RATE_LIMIT: int = 200
    EBAY_RATE_LIMIT: int = 200
    
    # Cache TTLs - Shorter for development
    MARKET_CACHE_TTL: int = 300  # 5 minutes
    PRODUCT_CACHE_TTL: int = 300  # 5 minutes
    TOKEN_CACHE_TTL: int = 300  # 5 minutes

    class Config:
        env_file = ".env.development" 