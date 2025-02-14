"""API endpoints for system monitoring."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict

from core.integrations.market_factory import MarketIntegrationFactory
from core.utils.redis import RedisClient
from core.exceptions.market import MarketIntegrationError

router = APIRouter()

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