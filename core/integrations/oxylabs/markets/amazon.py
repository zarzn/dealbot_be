"""Amazon-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union

from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class AmazonOxylabsService(OxylabsBaseService):
    """Service for scraping Amazon using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Amazon Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        self.source = "amazon_search"
        self.product_source = "amazon_product"

    async def search_products(
        self, 
        query: str, 
        country: str = "us", 
        limit: int = 20,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Amazon.
        
        Args:
            query: Search query
            country: Country domain (e.g. 'us', 'uk')
            limit: Maximum number of results
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with search results
        """
        # Map country code to domain (most countries use their code as domain)
        # Always convert to lowercase to ensure consistent handling
        country = country.lower() if country else "us"
        
        # Add debug logging before domain mapping
        logger.info(f"Amazon search - Original country code: {country}")
        
        # Handle special cases for domains
        domain_mapping = {
            "us": "com",  # US maps to .com domain
            "uk": "co.uk",
            "jp": "co.jp",
            "ca": "ca",
            "au": "com.au",
            "de": "de",
            "fr": "fr",
            "it": "it",
            "es": "es",
            "in": "in",
            "mx": "com.mx",
            "br": "com.br",
            "sg": "com.sg",
            "ae": "ae",
            "sa": "sa",
            "nl": "nl",
            "se": "se",
            "pl": "pl",
            "tr": "com.tr"
        }
        
        # Direct domain mapping - critical step!
        domain = domain_mapping.get(country, country)
        logger.info(f"Amazon search - Mapped domain from {country} to {domain}")
        
        # Create parameters according to Oxylabs API documentation
        params = {
            "source": self.source,
            "domain": domain,
            "query": query,
            "parse": parse,
        }
        
        # Explicitly log the source and domain for debugging
        logger.info(f"Amazon search - Using source: {self.source}")
        logger.info(f"Amazon search - Using domain: {domain}")
        
        # Add optional pagination parameters
        if "start_page" in kwargs:
            params["start_page"] = kwargs.pop("start_page")
            
        # Default to 1 page to match our limit parameter 
        # (maintaining backward compatibility)
        pages = kwargs.pop("pages", 1)
        params["pages"] = pages
        
        # Remove geo_location if it exists in kwargs to avoid API errors
        if "geo_location" in kwargs:
            logger.info("Removing geo_location parameter from Amazon search to avoid API errors")
            kwargs.pop("geo_location")
            
        # Handle category_id if provided
        if "category_id" in kwargs:
            params.setdefault("context", []).append({
                "key": "category_id",
                "value": kwargs.pop("category_id")
            })
            
        # Handle merchant_id if provided
        if "merchant_id" in kwargs:
            params.setdefault("context", []).append({
                "key": "merchant_id", 
                "value": kwargs.pop("merchant_id")
            })
            
        # Handle currency if provided
        if "currency" in kwargs:
            params.setdefault("context", []).append({
                "key": "currency",
                "value": kwargs.pop("currency")
            })
            
        # Add any remaining kwargs to the params
        params.update(kwargs)
        
        logger.debug(f"Amazon search params: {params}")
        
        return await self.scrape_url(params, cache_ttl=cache_ttl)

    async def get_product_details(
        self, 
        product_id: str, 
        country: str = "us", 
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on Amazon.
        
        Args:
            product_id: Amazon product ID (ASIN)
            country: Country domain (e.g. 'us', 'uk')
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        # Map country code to domain (most countries use their code as domain)
        # Always convert to lowercase to ensure consistent handling
        country = country.lower() if country else "us"
        
        # Add debug logging before domain mapping
        logger.info(f"Amazon product details - Original country code: {country}")
        
        # Handle special cases for domains
        domain_mapping = {
            "us": "com",  # US maps to .com domain
            "uk": "co.uk",
            "jp": "co.jp",
            "ca": "ca",
            "au": "com.au",
            "de": "de",
            "fr": "fr",
            "it": "it",
            "es": "es",
            "in": "in",
            "mx": "com.mx",
            "br": "com.br",
            "sg": "com.sg",
            "ae": "ae",
            "sa": "sa",
            "nl": "nl",
            "se": "se",
            "pl": "pl",
            "tr": "com.tr"
        }
        
        # Direct domain mapping - critical step!
        domain = domain_mapping.get(country, country)
        logger.info(f"Amazon product details - Mapped domain from {country} to {domain}")
            
        # Create parameters according to Oxylabs API documentation
        params = {
            "source": self.product_source,
            "domain": domain,
            "asin": product_id,
            "parse": parse
        }
        
        # Explicitly log the source and domain for debugging
        logger.info(f"Amazon product details - Using source: {self.product_source}")
        logger.info(f"Amazon product details - Using domain: {domain}")
        
        # Remove geo_location if it exists in kwargs to avoid API errors
        if "geo_location" in kwargs:
            logger.info("Removing geo_location parameter from Amazon product details to avoid API errors")
            kwargs.pop("geo_location")
        
        # Handle currency if provided
        if "currency" in kwargs:
            params.setdefault("context", []).append({
                "key": "currency",
                "value": kwargs.pop("currency")
            })
            
        # Add any remaining kwargs to the params
        params.update(kwargs)
        
        logger.debug(f"Amazon product details params: {params}")
        
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
            
            if not currency and "symbol" in raw_data:
                currency = detect_currency(raw_data["symbol"])
                
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
                "asin": raw_data.get("asin", None),
            }
        except Exception as e:
            logger.error(f"Error extracting Amazon product data: {e}")
            return {} 