"""Google Shopping-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union

from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class GoogleShoppingOxylabsService(OxylabsBaseService):
    """Service for scraping Google Shopping using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Google Shopping Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        self.source = "google_shopping_search"
        self.product_source = "google_shopping_product"

    async def search_products(
        self, 
        query: str,
        domain: str = "com",
        start_page: int = 1,
        pages: int = 1,
        limit: int = 10,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Google Shopping.
        
        Args:
            query: Search query
            domain: Domain localization for Google (e.g., 'com', 'co.uk')
            start_page: Starting page number
            pages: Number of pages to retrieve
            limit: Maximum number of results
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters including:
                - geo_location: Geographical location for results
                - locale: Accept-Language header value (interface language)
                - sort_by: Sort order (r=relevance, rv=reviews, p=price asc, pd=price desc)
                - min_price: Minimum price filter
                - max_price: Maximum price filter
                - results_language: Results language
                - nfpr: Turn off spelling auto-correction (true/false)
            
        Returns:
            OxylabsResult object with search results
        """
        # Create parameters according to Oxylabs API documentation
        params = {
            "source": self.source,
            "domain": domain,
            "query": query,
            "parse": parse,
            "start_page": start_page,
            "pages": pages,
            "limit": limit
        }
        
        # Build context array for additional parameters
        context = []
        
        # Add sorting parameter if provided
        if "sort_by" in kwargs:
            sort_by = kwargs.pop("sort_by")
            if sort_by in ["r", "rv", "p", "pd"]:
                context.append({"key": "sort_by", "value": sort_by})
        
        # Add price filters if provided
        if "min_price" in kwargs:
            min_price = kwargs.pop("min_price")
            context.append({"key": "min_price", "value": min_price})
            
        if "max_price" in kwargs:
            max_price = kwargs.pop("max_price")
            context.append({"key": "max_price", "value": max_price})
        
        # Add results language if provided
        if "results_language" in kwargs:
            results_language = kwargs.pop("results_language")
            context.append({"key": "results_language", "value": results_language})
            
        # Add nfpr (no spell correction) if provided
        if "nfpr" in kwargs:
            nfpr = kwargs.pop("nfpr")
            context.append({"key": "nfpr", "value": nfpr})
        
        # Add the context array if we have any parameters
        if context:
            params["context"] = context
        
        # Add geo_location if provided
        if "geo_location" in kwargs:
            params["geo_location"] = kwargs.pop("geo_location")
            
        # Add locale if provided
        if "locale" in kwargs:
            params["locale"] = kwargs.pop("locale")
            
        # Add user_agent_type if provided or default to desktop
        if "user_agent_type" in kwargs:
            params["user_agent_type"] = kwargs.pop("user_agent_type")
        else:
            params["user_agent_type"] = "desktop"
            
        # Add any remaining kwargs to the params
        params.update(kwargs)
        
        logger.debug(f"Google Shopping search params: {params}")
        
        return await self.scrape_url(params, cache_ttl=cache_ttl)

    async def get_product_details(
        self, 
        product_id: str,
        domain: str = "com",
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on Google Shopping.
        
        Args:
            product_id: Google Shopping product ID
            domain: Domain localization for Google (e.g., 'com', 'co.uk')
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters including:
                - geo_location: Geographical location for results
                - locale: Accept-Language header value (interface language)
            
        Returns:
            OxylabsResult object with product details
        """
        # Create parameters according to Oxylabs API documentation
        params = {
            "source": self.product_source,
            "domain": domain,
            "product_id": product_id,
            "parse": parse
        }
        
        # Add geo_location if provided
        if "geo_location" in kwargs:
            params["geo_location"] = kwargs.pop("geo_location")
            
        # Add locale if provided
        if "locale" in kwargs:
            params["locale"] = kwargs.pop("locale")
            
        # Add user_agent_type if provided or default to desktop
        if "user_agent_type" in kwargs:
            params["user_agent_type"] = kwargs.pop("user_agent_type")
        else:
            params["user_agent_type"] = "desktop"
            
        # Add any remaining kwargs to the params
        params.update(kwargs)
        
        logger.debug(f"Google Shopping product details params: {params}")
        
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
                    # Default to USD if detection fails
                    currency = "USD"
                    
            return {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "availability": raw_data.get("availability", None),
                "image_url": raw_data.get("image_url", None),
                "seller": raw_data.get("seller", None),
                "description": raw_data.get("description", ""),
                "item_id": raw_data.get("item_id", None),
                "variants": raw_data.get("variants", []),
                "category": raw_data.get("category", None),
            }
        except Exception as e:
            logger.error(f"Error extracting Google Shopping product data: {e}")
            return {} 