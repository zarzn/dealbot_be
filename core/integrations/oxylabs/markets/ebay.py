"""eBay-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union

from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class EbayOxylabsService(OxylabsBaseService):
    """Service for scraping eBay using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize eBay Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        self.source = "ebay_search"

    async def search_products(
        self, 
        query: str, 
        limit: int = 20, 
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on eBay.
        
        Args:
            query: Search query
            limit: Maximum number of results
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with search results
        """
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}"
        
        params = {
            "source": self.source,
            "url": url,
            "parse": parse,
            "render": "html",
            "limit": limit,
            "geo_location": kwargs.pop("geo_location", "United States"),
            **kwargs
        }
        
        return await self.scrape_url(params, cache_ttl=cache_ttl)

    async def get_product_details(
        self, 
        product_id: str, 
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on eBay.
        
        Args:
            product_id: eBay product ID
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        url = f"https://www.ebay.com/itm/{product_id}"
        
        params = {
            "source": self.source,
            "url": url,
            "parse": parse,
            "render": "html",
            "geo_location": kwargs.pop("geo_location", "United States"),
            **kwargs
        }
        
        return await self.scrape_url(params, cache_ttl=cache_ttl)

    def extract_product_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract useful product data from Oxylabs response.
        
        Args:
            raw_data: Raw data from Oxylabs response
            
        Returns:
            Dictionary with extracted product information
        """
        if not raw_data:
            return {}
            
        # Extract data from parsed results
        try:
            title = raw_data.get("title", "")
            price_text = raw_data.get("price", "")
            price_value, currency = extract_price(price_text)
            
            # If currency not detected, try to detect from locale or price text
            if not currency:
                currency = detect_currency(price_text)
                if not currency:
                    # Default to USD for eBay US
                    currency = "USD"
                    
            return {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "condition": raw_data.get("condition", None),
                "availability": raw_data.get("availability", None),
                "image_url": raw_data.get("image_url", None),
                "seller": raw_data.get("seller", None),
                "shipping": raw_data.get("shipping_price", None),
                "shipping_currency": raw_data.get("shipping_currency", currency),
                "returns": raw_data.get("returns", None),
                "description": raw_data.get("description", ""),
                "item_id": raw_data.get("item_id", None),
                "format": raw_data.get("format", None),  # auction, buy it now, etc.
                "location": raw_data.get("location", None),
            }
        except Exception as e:
            logger.error(f"Error extracting eBay product data: {e}")
            return {} 