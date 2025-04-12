"""Walmart-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union

from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class WalmartOxylabsService(OxylabsBaseService):
    """Service for scraping Walmart using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Walmart Walmart Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        self.source = "walmart_search"  # Try walmart_search as primary source
        self.universal_source = "universal"  # Fallback to universal if needed
        self.product_source = "universal"  # For product details, universal still works best

    async def search_products(
        self, 
        query: str, 
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: Optional[str] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Walmart.
        
        Args:
            query: Search query
            min_price: Minimum price filter
            max_price: Maximum price filter
            sort_by: Sorting option (price_low, price_high, best_seller, best_match)
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with search results
        """
        # Create parameters according to Oxylabs API documentation
        url = f"https://www.walmart.com/search?q={query}"
        
        # First try with the specific source - walmart_search
        try:
            params = {
                "source": self.source,
                "url": url,
                "parse": parse
            }
            
            # Log the source for debugging
            logger.info(f"Walmart search - Using specific source: {self.source}")
            logger.info(f"Walmart search - Using URL: {url}")
            
            # Add optional price filters
            if min_price is not None:
                params["min_price"] = min_price
                logger.info(f"Walmart search - Using min_price: {min_price}")
                
            if max_price is not None:
                params["max_price"] = max_price
                logger.info(f"Walmart search - Using max_price: {max_price}")
                
            # Add sort option if provided
            if sort_by is not None:
                # Map our sort options to Walmart's expected values
                sort_mapping = {
                    "price_asc": "price_low",
                    "price_desc": "price_high",
                    "best_selling": "best_seller",
                    "relevance": "best_match"
                }
                
                # Use mapped value if available, otherwise use provided value
                mapped_sort = sort_mapping.get(sort_by, sort_by)
                params["sort_by"] = mapped_sort
                logger.info(f"Walmart search - Mapped sort_by from {sort_by} to {mapped_sort}")
                
            # Add localization parameters if provided
            for param in ["domain", "fulfillment_speed", "fulfillment_type", "delivery_zip", "store_id"]:
                if param in kwargs:
                    params[param] = kwargs.pop(param)
                    logger.info(f"Walmart search - Using {param}: {params[param]}")
            
            # Special handling for geo_location - Walmart may use this differently than Amazon
            if "geo_location" in kwargs:
                geo_location = kwargs.pop("geo_location")
                logger.info(f"Walmart search - Using geo_location: {geo_location}")
                params["geo_location"] = geo_location
                    
            # Add any remaining kwargs to the params
            params.update(kwargs)
            
            # Log the final parameters for better debugging
            logger.info(f"Walmart search params: {params}")
            
            # Try with specific source
            result = await self.scrape_url(params, cache_ttl=cache_ttl)
            
            # If failed with specific source, try universal source as fallback
            if not result.success and "Unsupported source" in str(result.errors):
                logger.warning(f"Specific Walmart source failed, trying universal source as fallback")
                params["source"] = self.universal_source
                logger.info(f"Walmart search - Using fallback source: {self.universal_source}")
                result = await self.scrape_url(params, cache_ttl=cache_ttl)
                
            return result
            
        except Exception as e:
            logger.error(f"Error in Walmart search: {str(e)}")
            # Fall back to universal source on exception
            params["source"] = self.universal_source
            logger.info(f"Walmart search - Using fallback source after error: {self.universal_source}")
            return await self.scrape_url(params, cache_ttl=cache_ttl)

    async def get_product_details(
        self, 
        product_id: str, 
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on Walmart.
        
        Args:
            product_id: Walmart product ID
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        # Create parameters according to Oxylabs API documentation
        url = f"https://www.walmart.com/ip/{product_id}"
        
        params = {
            "source": self.product_source,
            "url": url,
            "parse": parse,
            "render": "html"
        }
        
        # Log the source for debugging
        logger.info(f"Walmart product details - Using source: {self.product_source}")
        logger.info(f"Walmart product details - Using URL: {url}")
        logger.info(f"Walmart product details - Using product_id: {product_id}")
        
        # Add localization parameters if provided
        for param in ["domain", "delivery_zip", "store_id"]:
            if param in kwargs:
                params[param] = kwargs.pop(param)
                logger.info(f"Walmart product details - Using {param}: {params[param]}")
                
        # Special handling for geo_location
        if "geo_location" in kwargs:
            geo_location = kwargs.pop("geo_location")
            logger.info(f"Walmart product details - Using geo_location: {geo_location}")
            params["geo_location"] = geo_location
                
        # Add any remaining kwargs to the params
        params.update(kwargs)
        
        # Log the final parameters for better debugging
        logger.info(f"Walmart product details params: {params}")
        
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
            
            if not currency:
                # Default to USD for Walmart
                currency = "USD"
                
            return {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "availability": raw_data.get("availability", None),
                "image_url": raw_data.get("image_url", None),
                "features": raw_data.get("features", []),
                "description": raw_data.get("description", ""),
                "seller": raw_data.get("seller", None),
                "item_id": raw_data.get("item_id", None),
            }
        except Exception as e:
            logger.error(f"Error extracting Walmart product data: {e}")
            return {} 