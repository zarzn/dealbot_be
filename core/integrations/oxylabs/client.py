"""Client factory for Oxylabs web scraping service."""

import asyncio
import json
import logging
import os
import re
import time
import hashlib
from typing import Dict, List, Optional, Any, Union, Tuple

import aiohttp
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.enums import MarketType
from core.integrations.oxylabs.market_base import OxylabsMarketBaseService
from core.integrations.oxylabs.markets.amazon import AmazonOxylabsService
from core.integrations.oxylabs.markets.walmart import WalmartOxylabsService
from core.integrations.oxylabs.markets.google_shopping import GoogleShoppingOxylabsService
from core.integrations.oxylabs.markets.ebay import EbayOxylabsService

logger = logging.getLogger(__name__)

# Country code to location mappings
COUNTRY_TO_LOCATION = {
    "us": "United States",
    "ca": "Canada",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "it": "Italy",
    "es": "Spain",
    "jp": "Japan",
    "cn": "China",
    "br": "Brazil",
    "mx": "Mexico",
    "in": "India",
    "ru": "Russia"
}


class OxylabsClient:
    """Factory class for creating Oxylabs service instances."""

    def __init__(
        self, 
        username: Optional[str] = None, 
        password: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ):
        """Initialize the Oxylabs client.
        
        Args:
            username: Oxylabs username (defaults to settings)
            password: Oxylabs password (defaults to settings)
            db: Database session for metrics recording
        """
        if username is None:
            username = settings.OXYLABS_USERNAME
            
        if password is None:
            # Handle password from settings, could be SecretStr or string
            if hasattr(settings.OXYLABS_PASSWORD, 'get_secret_value'):
                password = settings.OXYLABS_PASSWORD.get_secret_value()
            else:
                password = settings.OXYLABS_PASSWORD
        elif isinstance(password, SecretStr):
            password = password.get_secret_value()
            
        self.username = username
        self.password = password
        
        # Log credential status (without exposing values)
        logger.info(f"Initializing OxylabsClient with credentials: username={bool(username)}, password={bool(password)}")
            
        # Initialize service instances for each market
        self._services = {
            MarketType.AMAZON.value.lower(): AmazonOxylabsService(username, password),
            MarketType.WALMART.value.lower(): WalmartOxylabsService(username, password),
            MarketType.GOOGLE_SHOPPING.value.lower(): GoogleShoppingOxylabsService(username, password),
            MarketType.EBAY.value.lower(): EbayOxylabsService(username, password),
        }
        
        # Rate limiting properties
        self._rate_limit_lock = asyncio.Lock()
        self._request_times = []
        self._market_request_times = {
            market_type.value.lower(): [] 
            for market_type in MarketType
        }
        self._market_failures = {
            market_type.value.lower(): 0 
            for market_type in MarketType
        }
        self._rate_limited_markets = {}
        
        # URL validation cache
        self._url_cache = {}
        
        # Metrics tracking
        self.db = db
        self.metrics_service = None
        if db:
            try:
                from core.services.market_metrics import MarketMetricsService
                self.metrics_service = MarketMetricsService(db)
            except ImportError:
                logger.warning("Could not import MarketMetricsService, metrics tracking will be disabled")
        
        # Metrics batching
        self._metrics_batch = []
        self._metrics_batch_size = 10
        self._metrics_lock = asyncio.Lock()
        self._metrics_flush_task = None

    def get_service(self, market_type: MarketType) -> OxylabsMarketBaseService:
        """Get or create an Oxylabs service for the specified market.
        
        Args:
            market_type: Type of market to get service for
            
        Returns:
            OxylabsMarketBaseService instance for the specified market
            
        Raises:
            ValueError: If market_type is not supported
        """
        market_key = str(market_type.value).lower()
        
        if market_key not in self._services:
            if market_type == MarketType.AMAZON:
                service = AmazonOxylabsService(
                    username=self.username, password=self.password
                )
            elif market_type == MarketType.WALMART:
                service = WalmartOxylabsService(
                    username=self.username, password=self.password
                )
            elif market_type == MarketType.GOOGLE_SHOPPING:
                service = GoogleShoppingOxylabsService(
                    username=self.username, password=self.password
                )
            elif market_type == MarketType.EBAY:
                service = EbayOxylabsService(
                    username=self.username, password=self.password
                )
            else:
                raise ValueError(f"Unsupported market type: {market_type}")
                
            # Add metrics recording capability to the service
            original_record_metrics = service._record_metrics
            
            async def enhanced_record_metrics(
                market_type: str,
                success: bool = True,
                response_time: Optional[float] = None,
                error: Optional[str] = None
            ):
                # Call the original method first
                await original_record_metrics(market_type, success, response_time, error)
                
                # Also record metrics with our service
                await self._record_market_metrics(market_type, success, response_time, error)
                
            # Replace the method with our enhanced version
            service._record_metrics = enhanced_record_metrics
            
            self._services[market_key] = service
        
        return self._services[market_key]

    async def _apply_rate_limiting(self, market_type: str):
        """Apply rate limiting before making a request.
        
        Args:
            market_type: The market type to apply rate limiting for
        """
        async with self._rate_limit_lock:
            current_time = time.time()
            market_key = market_type.lower()
            
            # Check if market is rate limited
            if market_key in self._rate_limited_markets:
                expiry_time = self._rate_limited_markets[market_key]
                if expiry_time > current_time:
                    wait_time = expiry_time - current_time
                    logger.warning(f"Market {market_key} is rate limited. Waiting {wait_time:.2f}s")
                    await asyncio.sleep(min(wait_time, 30))  # Wait at most 30 seconds
                else:
                    # Expired, remove from rate limited markets
                    del self._rate_limited_markets[market_key]
            
            # Remove old request times
            cutoff_time = current_time - 60  # 1 minute ago
            self._request_times = [t for t in self._request_times if t > cutoff_time]
            
            # Check market-specific request times
            if market_key in self._market_request_times:
                self._market_request_times[market_key] = [
                    t for t in self._market_request_times[market_key] if t > cutoff_time
                ]
                
                # If too many requests in the last minute, add delay
                market_requests = len(self._market_request_times[market_key])
                if market_requests >= 10:  # 10 requests per minute per market
                    wait_time = 60 / 10  # 6 seconds between requests
                    logger.info(f"Market {market_key} approaching rate limit. Adding delay of {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
    
    def _record_request(self, market_type: str, success: bool = True):
        """Record a request for rate limiting purposes.
        
        Args:
            market_type: The market type the request was made for
            success: Whether the request was successful
        """
        current_time = time.time()
        market_key = market_type.lower()
        
        # Record request time
        self._request_times.append(current_time)
        
        # Record market-specific request time
        if market_key in self._market_request_times:
            self._market_request_times[market_key].append(current_time)
        
        # Handle failures
        if not success:
            if market_key in self._market_failures:
                self._market_failures[market_key] += 1
                
                # If too many failures, rate limit the market
                if self._market_failures[market_key] >= 5:
                    logger.warning(f"Too many failures for market {market_key}. Rate limiting for 5 minutes.")
                    self._rate_limited_markets[market_key] = current_time + 300  # 5 minutes
            else:
                self._market_failures[market_key] = 1
        else:
            # Reset failure count on success
            if market_key in self._market_failures:
                self._market_failures[market_key] = 0

    def _create_safe_copy(self, data: Any) -> Any:
        """Create a safe copy of data by removing potential circular references.
        
        Args:
            data: Data to create a safe copy of
            
        Returns:
            Safe copy of data
        """
        # Use a stack-based approach to avoid recursion depth issues
        if data is None:
            return None
            
        # Handle primitive types directly to reduce processing
        if isinstance(data, (str, int, float, bool, type(None))):
            return data
            
        # Handle dictionary type
        if isinstance(data, dict):
            # Create a new dict with safe copies of values
            result = {}
            # Skip these keys that could cause circular references or hold non-serializable data
            skip_keys = [
                "_client", "_service", "_session", "client", "service", "session",
                "connection", "connector", "_connector", "app", "_app", "request"
            ]
            
            for key, value in data.items():
                # Skip problematic keys
                if key in skip_keys:
                    continue
                    
                # Skip callable objects
                if callable(value):
                    continue
                    
                # Recursively create safe copies of values
                try:
                    safe_value = self._create_safe_copy(value)
                    if safe_value is not None:  # Skip None values to reduce output size
                        result[key] = safe_value
                except (RecursionError, TypeError, ValueError) as e:
                    # If error occurs, use a string representation instead
                    result[key] = f"<Complex object: {type(value).__name__}>"
                    logger.warning(f"Error creating safe copy of '{key}': {str(e)}")
                    
            return result
            
        # Handle list/tuple types
        elif isinstance(data, (list, tuple)):
            # Create a new list with safe copies of values
            result = []
            for item in data:
                try:
                    safe_item = self._create_safe_copy(item)
                    if safe_item is not None:  # Skip None values
                        result.append(safe_item)
                except (RecursionError, TypeError, ValueError) as e:
                    # If error occurs, use a string representation instead
                    result.append(f"<Complex object: {type(item).__name__}>")
                    logger.warning(f"Error creating safe copy of list item: {str(e)}")
                    
            return result
            
        # Handle sets
        elif isinstance(data, set):
            result = set()
            for item in data:
                try:
                    safe_item = self._create_safe_copy(item)
                    if safe_item is not None and isinstance(safe_item, (str, int, float, bool)):
                        # Only add hashable types to set
                        result.add(safe_item)
                except (RecursionError, TypeError, ValueError):
                    pass  # Skip problematic items in sets
            return result
            
        # For other types, try to convert to string if possible
        try:
            return str(data)
        except Exception:
            return f"<Object of type {type(data).__name__}>"

    def _extract_price(self, price_raw: Any) -> float:
        """Extract price from various formats.
        
        Args:
            price_raw: Price in various formats (string, float, dict)
            
        Returns:
            Extracted price as float or 0.0 if not extractable
        """
        if not price_raw:
            return 0.0
            
        # Handle numeric prices
        if isinstance(price_raw, (int, float)):
            return float(price_raw)
        
        # Handle string prices
        if isinstance(price_raw, str):
            # Remove currency symbols and whitespace
            price_str = price_raw.strip().replace('$', '').replace('£', '').replace('€', '')
            
            # Extract digits and decimal point
            price_match = re.search(r'(\d+\.?\d*|\.\d+)', price_str)
            if price_match:
                try:
                    return float(price_match.group(0))
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert price string to float: {price_raw}")
                    return 0.0
        
        # Handle dictionary with price key
        if isinstance(price_raw, dict):
            if 'value' in price_raw:
                return self._extract_price(price_raw['value'])
            if 'price' in price_raw:
                return self._extract_price(price_raw['price'])
        
        # Could not extract price
        logger.warning(f"Could not extract price from: {price_raw}")
        return 0.0

    def _extract_currency(self, price_raw: Any) -> Optional[str]:
        """Extract currency from price string or dict.
        
        Args:
            price_raw: Price in various formats (string, float, dict)
            
        Returns:
            Currency code (USD, EUR, GBP, etc.) or None if not extractable
        """
        if not price_raw:
            return None
        
        # Handle dictionary with currency key
        if isinstance(price_raw, dict):
            if 'currency' in price_raw:
                return price_raw['currency']
            if 'currency_code' in price_raw:
                return price_raw['currency_code']
        
        # Handle string prices
        if isinstance(price_raw, str):
            price_str = price_raw.strip()
            
            # Check for currency symbols
            if price_str.startswith('$') or 'USD' in price_str:
                return 'USD'
            elif price_str.startswith('£') or 'GBP' in price_str:
                return 'GBP'
            elif price_str.startswith('€') or 'EUR' in price_str:
                return 'EUR'
            elif price_str.startswith('¥') or 'JPY' in price_str:
                return 'JPY'
        
        # Default to USD if we couldn't extract a currency
        return 'USD'

    async def search_amazon(
        self,
        query: str,
        limit: int = 10,
        page: int = 1,
        pages: int = 1,
        region: str = "us",
        sort_by: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        """
        Search for products on Amazon.
        
        Args:
            query: Search query
            limit: Maximum number of results to return (default: 10)
            page: Page number to retrieve (default: 1)
            pages: Number of pages to retrieve (default: 1)
            region: Amazon region (default: us)
            sort_by: Sort results by (default: None)
            min_price: Minimum price filter (default: None)
            max_price: Maximum price filter (default: None)
            cache_ttl: Cache time-to-live in seconds (default: None)
            **kwargs: Additional parameters for search
            
        Returns:
            Tuple of (success, products, errors)
        """
        # Convert region to lowercase for consistent handling
        region = region.lower() if region else "us"
        
        try:
            # Log the search request
            logger.info(f"OxylabsClient: Searching Amazon for '{query}' in region '{region}', page {page}, pages {pages}")
            
            # Get the Amazon service
            amazon_service = self.get_service(MarketType.AMAZON)
            
            # Execute the search
            result = await amazon_service.search_products(
                query=query,
                region=region,
                limit=limit,
                page=page,
                pages=pages,
                parse=True,
                cache_ttl=cache_ttl,
                sort_by=sort_by,
                min_price=min_price,
                max_price=max_price,
                **kwargs
            )
            
            # Record metrics for this request
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=result.success,
                response_time=None,  # Service handles timing
                error=None if result.success else "; ".join(result.errors or ["Unknown error"])
            )
            
            # Process the results
            products = []
            if result.success and result.results:
                # Extract products from the results
                # Amazon results can have different structures
                
                # Case 1: Deeply nested structure - results[0].content.results.{paid/organic}
                if isinstance(result.results, list) and len(result.results) > 0:
                    for result_item in result.results:
                        if isinstance(result_item, dict) and "content" in result_item:
                            content = result_item["content"]
                            
                            if isinstance(content, dict) and "results" in content:
                                results_section = content["results"]
                                
                                # Extract products from paid and organic sections
                                if isinstance(results_section, dict):
                                    # Process paid listings
                                    if "paid" in results_section and isinstance(results_section["paid"], list):
                                        logger.info(f"Found {len(results_section['paid'])} paid products in Amazon search results")
                                        products.extend(results_section["paid"])
                                    
                                    # Process organic listings
                                    if "organic" in results_section and isinstance(results_section["organic"], list):
                                        logger.info(f"Found {len(results_section['organic'])} organic products in Amazon search results")
                                        products.extend(results_section["organic"])
                
                # Case 2: Direct paid/organic structure at top level
                if not products and isinstance(result.results, dict):
                    # Check for paid listings
                    if "paid" in result.results and isinstance(result.results["paid"], list):
                        logger.info(f"Found {len(result.results['paid'])} paid products at top level")
                        products.extend(result.results["paid"])
                    
                    # Check for organic listings
                    if "organic" in result.results and isinstance(result.results["organic"], list):
                        logger.info(f"Found {len(result.results['organic'])} organic products at top level")
                        products.extend(result.results["organic"])
                    
                    # Check for content->results structure
                    if "content" in result.results and isinstance(result.results["content"], dict):
                        content = result.results["content"]
                        
                        # Direct paid/organic in content
                        if "paid" in content and isinstance(content["paid"], list):
                            logger.info(f"Found {len(content['paid'])} paid products in content")
                            products.extend(content["paid"])
                        
                        if "organic" in content and isinstance(content["organic"], list):
                            logger.info(f"Found {len(content['organic'])} organic products in content")
                            products.extend(content["organic"])
                        
                        # Check for nested results
                        if "results" in content and isinstance(content["results"], dict):
                            results = content["results"]
                            
                            if "paid" in results and isinstance(results["paid"], list):
                                logger.info(f"Found {len(results['paid'])} paid products in content.results")
                                products.extend(results["paid"])
                            
                            if "organic" in results and isinstance(results["organic"], list):
                                logger.info(f"Found {len(results['organic'])} organic products in content.results")
                                products.extend(results["organic"])
                
                # Case 3: Direct list of products
                if not products and isinstance(result.results, list):
                    logger.info(f"Found {len(result.results)} products as direct list")
                    products = result.results
                
                logger.info(f"Successfully extracted {len(products)} Amazon products")
            else:
                logger.warning(f"Amazon search failed or returned no results: {result.errors}")
            
            return result.success, products, result.errors or []
        except Exception as e:
            error_msg = f"Error searching Amazon: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Record metrics for this failed request
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=False,
                response_time=None,
                error=error_msg
            )
            
            return False, [], [error_msg]

    async def get_amazon_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Amazon.
        
        Args:
            product_id: Amazon product ID (ASIN)
            **kwargs: Additional parameters:
                - region: Country code (e.g., 'us', 'uk') (was 'country' in old API)
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing product details
        """
        await self._apply_rate_limiting("amazon")
        
        try:
            service = self.get_service(MarketType.AMAZON)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            # Handle backward compatibility for 'country' parameter
            region = kwargs.pop("region", None)
            if region is None and "country" in kwargs:
                region = kwargs.pop("country")
            if region is None:
                region = "us"  # Default to US
            
            result = await service.get_product_details(
                product_id=product_id,
                region=region,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("amazon", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error getting Amazon product: {str(e)}")
            self._record_request("amazon", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

    async def search_walmart(
        self,
        query: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search for products on Walmart.
        
        Args:
            query: Search query
            **kwargs: Additional parameters for search including:
                - limit/max_results: Maximum results to return (default: 10)
                - region: Region or country (default: United States)
                - sort_by: Sorting option
                - min_price: Minimum price filter
                - max_price: Maximum price filter
                - parse: Whether to parse the results (default: True)
                - cache_ttl: Cache time-to-live in seconds (None for no caching)
                - extract_details: Whether to extract details for each product (default: False)
                - batch_size: Number of products to process in a single batch (default: 10)
            
        Returns:
            Dictionary containing search results
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("Walmart search temporarily disabled for testing")
        return {
            "success": True,
            "results": [],
            "errors": ["Walmart search temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("walmart")
        
        try:
            service = self.get_service(MarketType.WALMART)
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            extract_details = kwargs.pop("extract_details", False)
            batch_size = kwargs.pop("batch_size", 10)
            
            result = await service.search_products(
                query=query,
                limit=limit,
                parse=parse,
                cache_ttl=cache_ttl,
                extract_details=extract_details,
                batch_size=batch_size,
                **kwargs
            )
            
            self._record_request("walmart", success=result.success)
            
            # Create a safe copy of the result to prevent recursion issues during serialization
            safe_result = {
                "success": result.success,
                "results": self._create_safe_copy(result.results),
                "errors": result.errors.copy() if hasattr(result, 'errors') and result.errors else []
            }
            
            # Add the source if available
            if hasattr(result, 'source') and result.source:
                safe_result["source"] = result.source
                
            return safe_result
            
        except Exception as e:
            logger.error(f"Error in Walmart search: {str(e)}")
            self._record_request("walmart", success=False)
            
            # Handle Pydantic validation errors specially
            if "validation error" in str(e).lower():
                logger.error(f"Validation error details: {str(e)}")
                
            # Return an error result in a consistent format
            return {
                "success": False,
                "results": [],
                "errors": [str(e)]
            }
        """

    async def get_walmart_product_details(
        self,
        product_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific Walmart product.
        
        Args:
            product_id: Walmart product ID
            **kwargs: Additional parameters
                - url: Direct product URL (optional, will be constructed if not provided)
                - region: Region code (default: US)
                - parse: Whether to parse the results (default: True)
                - cache_ttl: Cache time-to-live in seconds (None for no caching)
                
        Returns:
            Dictionary containing product details
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("Walmart product details temporarily disabled for testing")
        return {
            "success": True,
            "results": {},
            "errors": ["Walmart product details temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("walmart")
        
        try:
            walmart_service = self.get_service(MarketType.WALMART)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            # Get direct URL if provided, otherwise construct it
            url = kwargs.pop("url", None)
            if not url and product_id:
                # Safely construct Walmart product URL from ID
                # Use the service's URL construction if available
                if hasattr(walmart_service, "get_product_url") and callable(getattr(walmart_service, "get_product_url")):
                    url = walmart_service.get_product_url(product_id)
                else:
                    # Fallback URL construction
                    url = f"https://www.walmart.com/ip/{product_id}"
            
            if not url:
                raise ValueError("Either product_id or url must be provided")
            
            # Get product details
            result = await walmart_service.get_product_details(
                product_id=product_id,
                url=url,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("walmart", success=result.success)
            
            # Create a safe copy of the result to prevent recursion issues during serialization
            safe_result = {
                "success": result.success,
                "results": self._create_safe_copy(result.results),
                "errors": result.errors.copy() if hasattr(result, 'errors') and result.errors else []
            }
            
            # Add source if available
            if hasattr(result, 'source') and result.source:
                safe_result["source"] = result.source
                
            return safe_result
            
        except Exception as e:
            logger.error(f"Error getting Walmart product details: {str(e)}")
            self._record_request("walmart", success=False)
            
            # Return an error result in a consistent format
            return {
                "success": False,
                "results": {},
                "errors": [str(e)]
            }
        """

    async def search_google_shopping(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Google Shopping.
        
        Args:
            query: Search query
            **kwargs: Additional parameters:
                - limit: Maximum number of results (default: 10)
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
                - sort_by: Sort order (r=relevance, rv=reviews, p=price asc, pd=price desc)
                - min_price: Minimum price filter
                - max_price: Maximum price filter
                - extract_details: Whether to extract details for each product (default: False)
                - batch_size: Number of products to process in a single batch (default: 10)
            
        Returns:
            Dictionary containing search results
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("Google Shopping search temporarily disabled for testing")
        return {
            "success": True,
            "results": [],
            "errors": ["Google Shopping search temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("google_shopping")
        
        try:
            service = self.get_service(MarketType.GOOGLE_SHOPPING)
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            extract_details = kwargs.pop("extract_details", False)
            batch_size = kwargs.pop("batch_size", 10)
            
            # Log the query for debugging
            logger.debug(f"Google Shopping search - Query: '{query}'")
            
            result = await service.search_products(
                query=query,
                limit=limit,
                parse=parse,
                cache_ttl=cache_ttl,
                extract_details=extract_details,
                batch_size=batch_size,
                **kwargs
            )
            
            self._record_request("google_shopping", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error in Google Shopping search: {str(e)}")
            self._record_request("google_shopping", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}
        """

    async def get_google_shopping_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Google Shopping.
        
        Args:
            product_id: Google Shopping product ID
            **kwargs: Additional parameters:
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing product details
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("Google Shopping product details temporarily disabled for testing")
        return {
            "success": True,
            "results": {},
            "errors": ["Google Shopping product details temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("google_shopping")
        
        try:
            service = self.get_service(MarketType.GOOGLE_SHOPPING)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.get_product_details(
                product_id=product_id,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("google_shopping", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error getting Google Shopping product: {str(e)}")
            self._record_request("google_shopping", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}
        """

    async def search_ebay(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on eBay.
        
        Args:
            query: Search query string
            **kwargs: Additional parameters
                - page: Page number (default: 1)
                - limit: Number of results per page (default: 25)
                - region: Region code (default: US)
                - sort_by: Sort order (default: None)
                - min_price: Minimum price (default: None)
                - max_price: Maximum price (default: None)
                - parse: Whether to parse the results (default: True)
                - cache_ttl: Cache time-to-live in seconds (None for no caching)
                
        Returns:
            Dictionary containing search results
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("eBay search temporarily disabled for testing")
        return {
            "success": True,
            "results": [],
            "errors": ["eBay search temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("ebay")
        
        try:
            service = self.get_service(MarketType.EBAY)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            # Execute search
            result = await service.search(
                query=query,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("ebay", success=result.success)
            
            # Process and return results
            if result.success and parse:
                # Create a safe copy of the results to avoid serialization issues
                processed_results = []
                
                for item in result.results.get("organic", []):
                    try:
                        safe_item = self._create_safe_copy(item)
                        if safe_item is not None:  # Skip None values
                            processed_results.append(safe_item)
                    except (RecursionError, TypeError) as e:
                        logger.warning(f"Error processing eBay result: {str(e)}")
                
                # Create a safe copy of the full result
                return {
                    "success": result.success,
                    "results": processed_results,
                    "total": len(processed_results),
                    "errors": result.errors.copy() if hasattr(result, 'errors') and result.errors else []
                }
            
            # Return the raw result
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
            
        except Exception as e:
            logger.error(f"Error in eBay search: {str(e)}")
            self._record_request("ebay", success=False)
            
            # Return error response
            return {
                "success": False,
                "results": [],
                "errors": [str(e)]
            }
        """

    async def get_ebay_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on eBay.
        
        Args:
            product_id: eBay product ID
            **kwargs: Additional parameters
                - url: Direct product URL (optional, will be constructed if not provided)
                - region: Region code (default: US)
                - parse: Whether to parse the results (default: True)
                - cache_ttl: Cache time-to-live in seconds (None for no caching)
                
        Returns:
            Dictionary containing product details
        """
        # TEMPORARILY DISABLED FOR TESTING
        logger.info("eBay product details temporarily disabled for testing")
        return {
            "success": True,
            "results": {},
            "errors": ["eBay product details temporarily disabled for testing"]
        }
        
        # Original implementation (commented out)
        """
        await self._apply_rate_limiting("ebay")
        
        try:
            service = self.get_service(MarketType.EBAY)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            # Get direct URL if provided, otherwise construct it
            url = kwargs.pop("url", None)
            if not url and product_id:
                # Safely construct eBay product URL from ID
                # Use the service's URL construction if available
                if hasattr(service, "get_product_url") and callable(getattr(service, "get_product_url")):
                    url = service.get_product_url(product_id)
                else:
                    # Fallback URL construction
                    url = f"https://www.ebay.com/itm/{product_id}"
            
            if not url:
                raise ValueError("Either product_id or url must be provided")
            
            # Get product details
            result = await service.get_product_details(
                product_id=product_id,
                url=url,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("ebay", success=result.success)
            
            # Create a safe copy of the result to prevent recursion issues during serialization
            safe_result = {
                "success": result.success,
                "results": self._create_safe_copy(result.results),
                "errors": result.errors.copy() if hasattr(result, 'errors') and result.errors else []
            }
            
            # Add source if available
            if hasattr(result, 'source') and result.source:
                safe_result["source"] = result.source
                
            return safe_result
            
        except Exception as e:
            logger.error(f"Error getting eBay product details: {str(e)}")
            self._record_request("ebay", success=False)
            
            # Return an error result in a consistent format
            return {
                "success": False,
                "results": {},
                "errors": [str(e)]
            }
        """

    async def close(self):
        """Close all services and release resources."""
        # Flush any remaining metrics
        if self._metrics_batch:
            await self._flush_metrics_batch()
            
        # Close all services
        for service in self._services.values():
            await service.close()

    async def _record_market_metrics(
        self,
        market_type: str,
        success: bool = True,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Record metrics about API requests.
        
        This method batches metrics to reduce database load.
        
        Args:
            market_type: Type of market (amazon, walmart, etc.)
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if any
        """
        if not self.metrics_service:
            return
        
        async with self._metrics_lock:
            # Add to batch
            self._metrics_batch.append({
                "market_type": market_type,
                "success": success,
                "response_time": response_time,
                "error": error,
                "timestamp": time.time()
            })
            
            # If batch is full or this is a failure, flush immediately
            if len(self._metrics_batch) >= self._metrics_batch_size or not success:
                # Create a new task to avoid blocking
                if not self._metrics_flush_task or self._metrics_flush_task.done():
                    self._metrics_flush_task = asyncio.create_task(self._flush_metrics_batch())

    async def _flush_metrics_batch(self) -> None:
        """Flush the metrics batch to the database."""
        if not self.metrics_service:
            return
            
        # Work with a copy to avoid locking during database operations
        async with self._metrics_lock:
            batch_to_process = self._metrics_batch.copy()
            self._metrics_batch = []
        
        if not batch_to_process:
            return
            
        for metric in batch_to_process:
            try:
                await self.metrics_service.record_market_request(
                    market_type=MarketType(metric["market_type"]),
                    success=metric["success"],
                    response_time=metric["response_time"],
                    error=metric["error"]
                )
            except Exception as e:
                logger.error(f"Failed to record metrics: {e}")


# Singleton instance
_client_instance: Optional[OxylabsClient] = None


def get_oxylabs_client(db: Optional[AsyncSession] = None) -> OxylabsClient:
    """Get or create a singleton OxylabsClient instance.
    
    Args:
        db: Optional database session for metrics recording
        
    Returns:
        OxylabsClient singleton instance
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = OxylabsClient(db=db)
    
    return _client_instance 