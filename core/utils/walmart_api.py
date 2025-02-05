"""Walmart Open API client.

This module provides a client for interacting with Walmart's Open API
to search for products and retrieve product information.
"""

import asyncio
from datetime import datetime
import json
import logging
from typing import Dict, List, Optional, Any
import urllib.parse
import aiohttp
import time

from core.exceptions import (
    MarketConnectionError,
    MarketRateLimitError,
    MarketAuthenticationError,
    InvalidDealDataError
)
from core.config import settings
from .web_crawler import WebCrawler

logger = logging.getLogger(__name__)

class WalmartAPI:
    """Walmart Open API client."""
    
    def __init__(
        self,
        api_key: str,
        affiliate_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        rate_limit: float = 1.0
    ):
        """Initialize the Walmart API client.
        
        Args:
            api_key: Walmart API key
            affiliate_id: Walmart affiliate ID (optional)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            rate_limit: Minimum time between requests in seconds
        """
        self.api_key = api_key
        self.affiliate_id = affiliate_id
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        
        self.base_url = "https://api.walmart.com/v3/items"
        self.search_url = "https://api.walmart.com/v3/search"
        
        self.last_request_time = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.web_crawler = WebCrawler(
            max_retries=max_retries,
            timeout=timeout,
            rate_limit=rate_limit
        )

    async def __aenter__(self):
        """Create aiohttp session on context manager enter."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session on context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication.
        
        Returns:
            Dictionary of request headers
        """
        headers = {
            "WM_SEC.KEY_VERSION": "1",
            "WM_CONSUMER.ID": self.api_key,
            "Accept": "application/json"
        }
        
        if self.affiliate_id:
            headers["WM_AFFILIATE.ID"] = self.affiliate_id
            
        return headers

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make authenticated request to Walmart API.
        
        Args:
            url: API endpoint URL
            params: URL parameters
            retry_count: Current retry attempt number
            
        Returns:
            API response data
            
        Raises:
            MarketConnectionError: If connection fails after all retries
            MarketRateLimitError: If rate limit is exceeded
            MarketAuthenticationError: If authentication fails
        """
        if not self.session:
            raise RuntimeError("WalmartAPI must be used as a context manager")

        self._enforce_rate_limit()
        
        try:
            async with self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            ) as response:
                if response.status == 429:
                    raise MarketRateLimitError(
                        market="walmart",
                        message="Walmart API rate limit exceeded"
                    )
                
                if response.status == 401:
                    raise MarketAuthenticationError(
                        market="walmart",
                        message="Walmart API authentication failed"
                    )
                
                if response.status >= 400:
                    if retry_count < self.max_retries:
                        await asyncio.sleep(2 ** retry_count)
                        return await self._make_request(
                            url,
                            params,
                            retry_count + 1
                        )
                    raise MarketConnectionError(
                        market="walmart",
                        message=f"Walmart API request failed: {response.status}"
                    )
                
                return await response.json()

        except asyncio.TimeoutError:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(url, params, retry_count + 1)
            raise MarketConnectionError(
                market="walmart",
                message="Walmart API request timed out"
            )

        except Exception as e:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(url, params, retry_count + 1)
            raise MarketConnectionError(
                market="walmart",
                message=str(e)
            )

    async def get_product(self, item_id: str) -> Dict[str, Any]:
        """Get product information by item ID.
        
        Args:
            item_id: Walmart item ID
            
        Returns:
            Product data dictionary
            
        Raises:
            InvalidDealDataError: If product data is invalid or missing required fields
        """
        url = f"{self.base_url}/{item_id}"
        
        try:
            response = await self._make_request(url)
            
            # Extract required fields
            data = {
                "title": response.get("name"),
                "url": response.get("productTrackingUrl") or f"https://www.walmart.com/ip/{item_id}",
                "source": "walmart",
                "item_id": item_id
            }

            # Extract price information
            if price_info := response.get("price", {}):
                data["price"] = float(price_info.get("currentPrice", 0))
                data["currency"] = price_info.get("currencyUnit", "USD")
                
                if list_price := price_info.get("listPrice"):
                    data["original_price"] = float(list_price)

            # Extract image URL
            if images := response.get("imageInfo", {}).get("allImages", []):
                data["image_url"] = images[0].get("url")

            # Extract description
            if long_description := response.get("longDescription"):
                data["description"] = long_description
            elif short_description := response.get("shortDescription"):
                data["description"] = short_description

            # Validate required fields
            if not all(k in data for k in ["title", "price", "url"]):
                raise InvalidDealDataError(
                    message="Missing required product data",
                    details={
                        "item_id": item_id,
                        "available_fields": list(data.keys())
                    }
                )

            return data

        except (MarketConnectionError, MarketRateLimitError, MarketAuthenticationError):
            # On API failure, try web scraping as fallback
            logger.warning(f"Walmart API failed, falling back to web scraping for item ID: {item_id}")
            url = f"https://www.walmart.com/ip/{item_id}"
            async with self.web_crawler as crawler:
                return await crawler.extract_product_data(url)

    async def search_products(
        self,
        query: str,
        category_id: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort: str = "best_match",
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Search for products.
        
        Args:
            query: Search query
            category_id: Category ID filter
            min_price: Minimum price filter
            max_price: Maximum price filter
            sort: Sort order (best_match, price_low, price_high, best_seller, etc.)
            limit: Maximum number of results to return
            
        Returns:
            List of product data dictionaries
        """
        params = {
            "query": query,
            "sort": sort,
            "limit": limit
        }

        if category_id:
            params["categoryId"] = category_id
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price

        response = await self._make_request(self.search_url, params)
        
        if "items" not in response:
            return []

        results = []
        for item in response["items"]:
            try:
                # Get full product details for each search result
                product = await self.get_product(item["itemId"])
                results.append(product)
            except Exception as e:
                logger.warning(f"Failed to get details for item {item['itemId']}: {e}")
                continue

        return results 
