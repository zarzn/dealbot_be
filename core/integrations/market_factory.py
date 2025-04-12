"""Market integration factory."""

from typing import List, Dict, Any, Optional, Literal
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
        db: Optional[AsyncSession] = None,
        scraper_type: Literal["scraper_api", "oxylabs"] = settings.SCRAPER_TYPE
    ):
        """Initialize the factory with optional settings.
        
        Args:
            redis_client: Redis client for caching
            api_key: API key for scraper service (if using ScraperAPI)
            db: Database session for tracking metrics
            scraper_type: Type of scraper to use ("scraper_api" or "oxylabs")
        """
        self.redis_client = redis_client
        self.api_key = api_key
        self.db = db
        self.scraper_type = scraper_type
        self._scraper_api_instance = None
        self._oxylabs_instance = None
        
    async def get_scraper_api_service(self) -> Any:
        """Get a ScraperAPIService instance with lazy import to avoid circular dependencies."""
        if self._scraper_api_instance:
            return self._scraper_api_instance
            
        # Import here to avoid circular dependency
        from core.integrations.scraper_api import ScraperAPIService
        
        self._scraper_api_instance = ScraperAPIService(
            api_key=self.api_key or settings.SCRAPER_API_KEY,
            redis_client=self.redis_client,
            db=self.db
        )
        return self._scraper_api_instance
        
    async def get_oxylabs_service(self) -> Any:
        """Get an OxylabsService instance with lazy import to avoid circular dependencies."""
        if self._oxylabs_instance:
            return self._oxylabs_instance
            
        # Import here to avoid circular dependency
        from core.integrations.oxylabs import get_oxylabs
        
        self._oxylabs_instance = await get_oxylabs(
            db=self.db
        )
        return self._oxylabs_instance
        
    async def get_scraper_service(self):
        """Get the appropriate scraper service based on the configured type."""
        if self.scraper_type == "oxylabs":
            return await self.get_oxylabs_service()
        else:
            return await self.get_scraper_api_service()

    async def search_products(
        self,
        market: str,
        query: str,
        page: int = 1,
        limit: int = 15,
        geo_location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for products in the specified market.
        
        Args:
            market: Market identifier (amazon, walmart, google_shopping, ebay)
            query: Search query string
            page: Result page number (ignored in simplified API)
            limit: Maximum number of products to return (default: 15)
            geo_location: Geographic location for localized results (optional)
            
        Returns:
            List of product dictionaries or dictionary with 'results' field containing product list
        """
        import logging
        logger = logging.getLogger(__name__)
        
        scraper = await self.get_scraper_service()
        
        if market.lower() == "amazon":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                result = await scraper.search_amazon(query, **kwargs)
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Amazon search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                return await scraper.search_amazon(query, limit=limit)
        elif market.lower() == "walmart":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                result = await scraper.search_walmart(query, **kwargs)
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Walmart search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                return await scraper.search_walmart(query, limit=limit)
        elif market.lower() == "google_shopping":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                result = await scraper.search_google_shopping(query, **kwargs)
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Google Shopping search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                return await scraper.search_google_shopping(query, limit=limit)
        elif market.lower() == "ebay":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                result = await scraper.search_ebay(query, **kwargs)
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Ebay search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                # Use ScraperAPI as fallback
                scraper_api = await self.get_scraper_api_service()
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
        product_id: str,
        geo_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed information for a specific product.
        
        Args:
            market: Market identifier (amazon, walmart, google_shopping, ebay)
            product_id: Product identifier (asin, item_id, etc.)
            geo_location: Geographic location for localized results (optional)
            
        Returns:
            Product details dictionary
        """
        scraper = await self.get_scraper_service()
        
        if market.lower() == "amazon":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_amazon_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_amazon_product(product_id)
        elif market.lower() == "walmart":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_walmart_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_walmart_product(product_id)
        elif market.lower() == "google_shopping":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_google_shopping_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_google_shopping_product(product_id)
        elif market.lower() == "ebay":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_ebay_product(product_id, geo_location=geo_location)
            else:
                if self.scraper_type == "oxylabs":
                    return await scraper.get_ebay_product(product_id)
                else:
                    # Use ScraperAPI as fallback
                    scraper_api = await self.get_scraper_api_service()
                    return await scraper_api.get_ebay_product(product_id)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="get_product_details",
                reason=f"Unsupported market: {market}"
            )