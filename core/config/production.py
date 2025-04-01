from typing import List
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    # Application
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Security - Strict settings for production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS - Restrict to specific origins in production
    CORS_ORIGINS: List[str] = [
        "https://rebaton.ai",
        "https://deals.yourdomain.com",
        "https://api.deals.yourdomain.com",
        "https://d3irpl0o2ddv9y.cloudfront.net"
    ]
    CORS_CREDENTIALS: bool = True
    
    # Rate Limiting - Stricter in production
    RATE_LIMIT_PER_SECOND: int = 5
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # Structured logging for production
    
    # Redis - SSL required in production
    REDIS_SSL: bool = True
    REDIS_POOL_SIZE: int = 20
    REDIS_TIMEOUT: int = 3
    
    # Market Rate Limits - Conservative for production
    MARKET_DEFAULT_RATE_LIMIT: int = 50
    AMAZON_RATE_LIMIT: int = 50
    WALMART_RATE_LIMIT: int = 50
    EBAY_RATE_LIMIT: int = 50
    
    # Cache TTLs - Longer for production
    MARKET_CACHE_TTL: int = 3600  # 1 hour
    PRODUCT_CACHE_TTL: int = 1800  # 30 minutes
    TOKEN_CACHE_TTL: int = 3000  # 50 minutes
    
    # Additional Production Settings
    SENTRY_DSN: str = ""  # Sentry error tracking
    PROMETHEUS_ENABLED: bool = True
    HEALTH_CHECK_ENABLED: bool = True
    BACKUP_ENABLED: bool = True
    SSL_REQUIRED: bool = True
    
    # Performance Tuning
    WORKER_CONNECTIONS: int = 1000
    KEEPALIVE_TIMEOUT: int = 65
    MAX_REQUESTS_JITTER: int = 50
    MAX_REQUESTS: int = 1000
    
    class Config:
        env_file = ".env.production" 