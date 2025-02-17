"""Market integration factory."""

from typing import List, Dict, Any, Optional
from pydantic import SecretStr

from core.config import get_settings
from core.exceptions.market_exceptions import MarketIntegrationError
from .scraper_api import ScraperAPIService

settings = get_settings()

class MarketIntegrationFactory:
    """Factory for market integrations."""

    def __init__(
        self,
        redis_client=None,
        api_key: Optional[SecretStr] = None
    ):
        """Initialize factory."""
        self.redis_client = redis_client
        self._scraper_api = None
        self._api_key = api_key or settings.SCRAPER_API_KEY

    @property
    def scraper_api(self) -> ScraperAPIService:
        """Get or create ScraperAPI service."""
        if not self._scraper_api:
            self._scraper_api = ScraperAPIService(
                api_key=self._api_key,
                redis_client=self.redis_client
            )
        return self._scraper_api

    async def search_products(
        self,
        market: str,
        query: str,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """Search for products in the specified market."""
        if market.lower() == "amazon":
            return await self.scraper_api.search_amazon(query, page)
        elif market.lower() == "walmart":
            return await self.scraper_api.search_walmart_products(query, page)
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
        if market.lower() == "amazon":
            return await self.scraper_api.get_amazon_product(product_id)
        elif market.lower() == "walmart":
            return await self.scraper_api.get_walmart_product(product_id)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="get_product_details",
                reason=f"Unsupported market: {market}"
            )