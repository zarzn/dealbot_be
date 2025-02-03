"""Redis configuration.

This module provides Redis configuration settings for the application.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    REDIS_HOST: str = Field(
        default="localhost",
        description="Redis host"
    )
    
    REDIS_PORT: int = Field(
        default=6379,
        description="Redis port"
    )
    
    REDIS_DB: int = Field(
        default=0,
        description="Redis database number"
    )
    
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        description="Redis password"
    )
    
    REDIS_SSL: bool = Field(
        default=False,
        description="Use SSL for Redis connection"
    )
    
    REDIS_POOL_SIZE: int = Field(
        default=10,
        description="Redis connection pool size"
    )
    
    REDIS_POOL_TIMEOUT: int = Field(
        default=30,
        description="Redis connection pool timeout in seconds"
    )
    
    REDIS_SOCKET_TIMEOUT: int = Field(
        default=5,
        description="Redis socket timeout in seconds"
    )
    
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(
        default=5,
        description="Redis socket connect timeout in seconds"
    )
    
    REDIS_RETRY_ON_TIMEOUT: bool = Field(
        default=True,
        description="Retry on Redis timeout"
    )
    
    REDIS_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of Redis retries"
    )
    
    REDIS_RETRY_INTERVAL: int = Field(
        default=1,
        description="Redis retry interval in seconds"
    )
    
    # Cache settings
    CACHE_DEFAULT_TTL: int = Field(
        default=3600,  # 1 hour
        description="Default cache TTL in seconds"
    )
    
    CACHE_LONG_TTL: int = Field(
        default=86400,  # 24 hours
        description="Long-term cache TTL in seconds"
    )
    
    CACHE_SHORT_TTL: int = Field(
        default=300,  # 5 minutes
        description="Short-term cache TTL in seconds"
    )
    
    # Rate limiting settings
    RATE_LIMIT_DEFAULT_LIMIT: int = Field(
        default=100,
        description="Default rate limit per minute"
    )
    
    RATE_LIMIT_WINDOW: int = Field(
        default=60,  # 1 minute
        description="Rate limit window in seconds"
    )
    
    # Lock settings
    LOCK_DEFAULT_TIMEOUT: int = Field(
        default=30,
        description="Default lock timeout in seconds"
    )
    
    LOCK_EXTEND_THRESHOLD: float = Field(
        default=0.8,
        description="Lock extend threshold (percentage of timeout)"
    )
    
    class Config:
        """Pydantic model configuration."""
        
        env_prefix = ""
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create settings instance
redis_settings = RedisSettings() 