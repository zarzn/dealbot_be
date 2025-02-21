"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from core.database import get_async_db_session as get_db
from core.integrations.market_factory import MarketIntegrationFactory
from core.utils.redis import RedisClient
from core.exceptions.market_exceptions import MarketIntegrationError

router = APIRouter()

@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Check database connection
        await db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "message": "System is operational"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "message": str(e)
        }

@router.get("/scraper-api/usage", response_model=Dict[str, int])
async def get_scraper_api_usage():
    """Get current ScraperAPI credit usage."""
    try:
        market_factory = MarketIntegrationFactory()
        return await market_factory.get_credit_usage()
    except MarketIntegrationError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/redis")
async def check_redis():
    """Check Redis connection."""
    try:
        redis = RedisClient()
        await redis.ping()
        return {
            "status": "healthy",
            "message": "Redis is connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": str(e)
        } 