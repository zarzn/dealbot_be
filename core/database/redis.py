"""Redis connection module."""
import aioredis
from typing import Optional
from core.config import get_settings
from core.logger import logger
from core.constants import REDIS_MAX_CONNECTIONS, REDIS_POOL_SIZE, REDIS_TIMEOUT

_redis_pool: Optional[aioredis.Redis] = None

async def init_redis_pool() -> None:
    """Initialize Redis connection pool."""
    global _redis_pool
    try:
        if not _redis_pool:
            settings = get_settings()
            _redis_pool = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                **settings.get_redis_pool_settings()
            )
            logger.info("Redis connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis connection pool: {str(e)}")
        # Don't raise the error in development, just log it
        if get_settings().APP_ENV != "development":
            raise

async def get_redis() -> Optional[aioredis.Redis]:
    """Get Redis connection from pool."""
    if not _redis_pool:
        await init_redis_pool()
    return _redis_pool

async def close_redis_pool() -> None:
    """Close Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection pool closed") 