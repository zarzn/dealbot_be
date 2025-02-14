"""Market integration factory module."""

from typing import Dict, Optional, Type
from core.integrations.scraper_api import ScraperAPIService
from core.exceptions.market import MarketIntegrationError
from core.utils.redis import RedisClient

class MarketIntegrationFactory:
    """Factory for creating market integration instances."""
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        self.redis_client = redis_client or RedisClient()
        self._scraper_api = None
        
    @property
    def scraper_api(self) -> ScraperAPIService:
        """Get or create ScraperAPI service instance."""
        if not self._scraper_api:
            self._scraper_api = ScraperAPIService(
                redis_client=self.redis_client
            )
        return self._scraper_api
    
    async def search_products(self, market: str, query: str, page: int = 1):
        """Search products across different markets."""
        if market.lower() == 'amazon':
            return await self.scraper_api.search_amazon_products(query, page)
        elif market.lower() == 'walmart':
            return await self.scraper_api.search_walmart_products(query, page)
        else:
            raise MarketIntegrationError(
                f"Unsupported market: {market}"
            )
    
    async def get_product(self, market: str, product_id: str):
        """Get product details from different markets."""
        if market.lower() == 'amazon':
            return await self.scraper_api.get_amazon_product(product_id)
        elif market.lower() == 'walmart':
            return await self.scraper_api.get_walmart_product(product_id)
        else:
            raise MarketIntegrationError(
                f"Unsupported market: {market}"
            )
    
    async def get_credit_usage(self):
        """Get ScraperAPI credit usage."""
        return await self.scraper_api.get_credit_usage() 