"""Market integration factory."""

from typing import List, Dict, Any, Optional
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions.market_exceptions import MarketIntegrationError

settings = get_settings()

class MarketIntegrationFactory:
    """Factory for market integrations."""

    def __init__(
        self,
        redis_client=None,
        api_key: Optional[SecretStr] = None,
        db: Optional[AsyncSession] = None
    ):
        """Initialize the factory with optional settings."""
        self.redis_client = redis_client
        self.api_key = api_key
        self.db = db
        self._instance = None
        
    async def get_scraper_api_service(self) -> Any:
        """Get a ScraperAPIService instance with lazy import to avoid circular dependencies."""
        if self._instance:
            return self._instance
            
        # Import here to avoid circular dependency
        from .scraper_api import ScraperAPIService
        
        self._instance = ScraperAPIService(
            api_key=self.api_key or settings.SCRAPER_API_KEY,
            redis_client=self.redis_client,
            db=self.db
        )
        return self._instance

    async def search_products(
        self,
        market: str,
        query: str,
        page: int = 1,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Search for products in the specified market.
        
        Args:
            market: Market identifier (amazon, walmart, google_shopping, ebay)
            query: Search query string
            page: Result page number (ignored in simplified API)
            limit: Maximum number of products to return (default: 15)
            
        Returns:
            List of product dictionaries
        """
        scraper_api = await self.get_scraper_api_service()
        if market.lower() == "amazon":
            return await scraper_api.search_amazon(query, limit=limit)
        elif market.lower() == "walmart":
            return await scraper_api.search_walmart(query, limit=limit)
        elif market.lower() == "google_shopping":
            return await scraper_api.search_google_shopping(query, limit=limit)
        elif market.lower() == "ebay":
            return await scraper_api.search_ebay(query, limit=limit)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="search_products",
                reason=f"Unsupported market: {market}"
            )

    async def get_product_details(
        self,
        market: str,
        product_id: str
    ) -> Dict[str, Any]:
        """Get product details from the specified market."""
        scraper_api = await self.get_scraper_api_service()
        if market.lower() == "amazon":
            return await scraper_api.get_amazon_product(product_id)
        elif market.lower() == "walmart":
            return await scraper_api.get_walmart_product(product_id)
        elif market.lower() == "google_shopping":
            return await scraper_api.get_google_shopping_product(product_id)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="get_product_details",
                reason=f"Unsupported market: {market}"
            )