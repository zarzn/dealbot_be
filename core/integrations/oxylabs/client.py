"""Client factory for Oxylabs web scraping service."""

import asyncio
import json
import logging
import os
import re
import time
import hashlib
from typing import Dict, List, Optional, Any, Union

import aiohttp
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.enums import MarketType
from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
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

    def get_service(self, market_type: MarketType) -> OxylabsBaseService:
        """Get or create an Oxylabs service for the specified market.
        
        Args:
            market_type: Type of market to get service for
            
        Returns:
            OxylabsBaseService instance for the specified market
            
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

    async def search_amazon(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Amazon.
        
        Args:
            query: Search query
            **kwargs: Additional parameters:
                - country: Country domain (default: "us")
                - limit: Maximum number of results (default: 10)
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing search results
        """
        await self._apply_rate_limiting("amazon")
        
        try:
            service = self.get_service(MarketType.AMAZON)
            country = kwargs.pop("country", "us")
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.search_products(
                query=query,
                country=country,
                limit=limit,
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
            logger.error(f"Error in Amazon search: {str(e)}")
            self._record_request("amazon", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

    async def get_amazon_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Amazon.
        
        Args:
            product_id: Amazon product ID (ASIN)
            **kwargs: Additional parameters:
                - country: Country domain (default: "us")
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing product details
        """
        await self._apply_rate_limiting("amazon")
        
        try:
            service = self.get_service(MarketType.AMAZON)
            country = kwargs.pop("country", "us")
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.get_product_details(
                product_id=product_id,
                country=country,
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

    async def search_walmart(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Walmart.
        
        Args:
            query: Search query
            **kwargs: Additional parameters:
                - limit: Maximum number of results (default: 10)
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing search results
        """
        await self._apply_rate_limiting("walmart")
        
        try:
            service = self.get_service(MarketType.WALMART)
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.search_products(
                query=query,
                limit=limit,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("walmart", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error in Walmart search: {str(e)}")
            self._record_request("walmart", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

    async def get_walmart_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Walmart.
        
        Args:
            product_id: Walmart product ID
            **kwargs: Additional parameters:
                - parse: Whether to parse results (default: True)
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing product details
        """
        await self._apply_rate_limiting("walmart")
        
        try:
            service = self.get_service(MarketType.WALMART)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.get_product_details(
                product_id=product_id,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("walmart", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error getting Walmart product: {str(e)}")
            self._record_request("walmart", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

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
            
        Returns:
            Dictionary containing search results
        """
        await self._apply_rate_limiting("google_shopping")
        
        try:
            service = self.get_service(MarketType.GOOGLE_SHOPPING)
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.search_products(
                query=query,
                limit=limit,
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
            logger.error(f"Error in Google Shopping search: {str(e)}")
            self._record_request("google_shopping", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

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

    async def search_ebay(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on eBay.
        
        Args:
            query: Search query
            **kwargs: Additional parameters:
                - limit: Maximum number of results (default: 10)
                - parse: Whether to parse results (default: True)
                - geo_location: Geographical location (default: "United States")
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing search results
        """
        await self._apply_rate_limiting("ebay")
        
        try:
            service = self.get_service(MarketType.EBAY)
            limit = kwargs.pop("limit", kwargs.pop("max_results", 10))
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.search_products(
                query=query,
                limit=limit,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("ebay", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error in eBay search: {str(e)}")
            self._record_request("ebay", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

    async def get_ebay_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on eBay.
        
        Args:
            product_id: eBay product ID
            **kwargs: Additional parameters:
                - parse: Whether to parse results (default: True)
                - geo_location: Geographical location (default: "United States")
                - cache_ttl: Cache time-to-live in seconds (default: None)
            
        Returns:
            Dictionary containing product details
        """
        await self._apply_rate_limiting("ebay")
        
        try:
            service = self.get_service(MarketType.EBAY)
            parse = kwargs.pop("parse", True)
            cache_ttl = kwargs.pop("cache_ttl", None)
            
            result = await service.get_product_details(
                product_id=product_id,
                parse=parse,
                cache_ttl=cache_ttl,
                **kwargs
            )
            
            self._record_request("ebay", success=result.success)
            
            return {
                "success": result.success,
                "results": result.results,
                "errors": result.errors
            }
        except Exception as e:
            logger.error(f"Error getting eBay product: {str(e)}")
            self._record_request("ebay", success=False)
            return {"success": False, "results": [], "errors": [str(e)]}

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