"""Amazon Product Advertising API client.

This module provides a client for interacting with Amazon's Product Advertising API
to search for products and retrieve product information.
"""

import asyncio
from datetime import datetime
import hashlib
import hmac
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

class AmazonAPI:
    """Amazon Product Advertising API client."""
    
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        partner_tag: str,
        region: str = "us-west-2",
        marketplace: str = "www.amazon.com",
        max_retries: int = 3,
        timeout: int = 30,
        rate_limit: float = 1.0
    ):
        """Initialize the Amazon API client.
        
        Args:
            access_key: AWS access key ID
            secret_key: AWS secret key
            partner_tag: Amazon Associate tag
            region: AWS region
            marketplace: Amazon marketplace domain
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            rate_limit: Minimum time between requests in seconds
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.partner_tag = partner_tag
        self.region = region
        self.marketplace = marketplace
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        
        self.service = "ProductAdvertisingAPI"
        self.host = f"webservices.{marketplace}"
        self.endpoint = f"https://{self.host}/paapi5/getitems"
        
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

    def _generate_signature(self, headers: Dict[str, str], request_params: str) -> str:
        """Generate AWS signature for request authentication.
        
        Args:
            headers: Request headers
            request_params: URL-encoded request parameters
            
        Returns:
            AWS signature string
        """
        canonical_request = "\n".join([
            "POST",
            "/paapi5/getitems",
            request_params,
            "\n".join(f"{k}:{v}" for k, v in sorted(headers.items())),
            "",
            "UNSIGNED-PAYLOAD"
        ])
        
        date = headers["x-amz-date"]
        credential_scope = f"{date[:8]}/{self.region}/{self.service}/aws4_request"
        
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest()
        ])
        
        k_date = hmac.new(
            f"AWS4{self.secret_key}".encode(),
            date[:8].encode(),
            hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, self.region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, self.service.encode(), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        
        return hmac.new(
            k_signing,
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

    async def _make_request(
        self,
        operation: str,
        payload: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make authenticated request to Amazon API.
        
        Args:
            operation: API operation name
            payload: Request payload
            retry_count: Current retry attempt number
            
        Returns:
            API response data
            
        Raises:
            MarketConnectionError: If connection fails after all retries
            MarketRateLimitError: If rate limit is exceeded
            MarketAuthenticationError: If authentication fails
        """
        if not self.session:
            raise RuntimeError("AmazonAPI must be used as a context manager")

        self._enforce_rate_limit()
        
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        headers = {
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-amz-date": timestamp,
            "x-amz-target": f"com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{operation}"
        }
        
        request_params = ""  # URL parameters not used for POST requests
        signature = self._generate_signature(headers, request_params)
        
        auth_header = (
            f"AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{timestamp[:8]}/{self.region}/"
            f"{self.service}/aws4_request, "
            f"SignedHeaders={';'.join(sorted(headers.keys()))}, "
            f"Signature={signature}"
        )
        headers["Authorization"] = auth_header

        try:
            async with self.session.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout
            ) as response:
                if response.status == 429:
                    raise MarketRateLimitError(
                        market="amazon",
                        message="Amazon API rate limit exceeded"
                    )
                
                if response.status == 401:
                    raise MarketAuthenticationError(
                        market="amazon",
                        message="Amazon API authentication failed"
                    )
                
                if response.status >= 400:
                    if retry_count < self.max_retries:
                        await asyncio.sleep(2 ** retry_count)
                        return await self._make_request(
                            operation,
                            payload,
                            retry_count + 1
                        )
                    raise MarketConnectionError(
                        market="amazon",
                        reason=f"Amazon API request failed: {response.status}"
                    )
                
                return await response.json()

        except asyncio.TimeoutError:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(
                    operation,
                    payload,
                    retry_count + 1
                )
            raise MarketConnectionError(
                market="amazon",
                reason="Amazon API request timed out"
            )

        except Exception as e:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(
                    operation,
                    payload,
                    retry_count + 1
                )
            raise MarketConnectionError(
                market="amazon",
                reason=str(e)
            )

    async def get_product(self, asin: str) -> Dict[str, Any]:
        """Get product information by ASIN.
        
        Args:
            asin: Amazon Standard Identification Number
            
        Returns:
            Product data dictionary
            
        Raises:
            InvalidDealDataError: If product data is invalid or missing required fields
        """
        payload = {
            "ItemIds": [asin],
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.marketplace,
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Images.Primary.Large",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo"
            ]
        }

        try:
            response = await self._make_request("GetItems", payload)
            
            if "ItemsResult" not in response:
                raise InvalidDealDataError(
                    message="Invalid Amazon API response",
                    details={"asin": asin}
                )

            items = response["ItemsResult"].get("Items", [])
            if not items:
                raise InvalidDealDataError(
                    message="Product not found",
                    details={"asin": asin}
                )

            item = items[0]
            
            # Extract required fields
            data = {
                "title": item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue"),
                "url": item.get("DetailPageURL"),
                "source": "amazon",
                "asin": asin
            }

            # Extract price information
            if offers := item.get("Offers", {}).get("Listings", []):
                price = offers[0].get("Price", {})
                data["price"] = float(price.get("Amount", 0))
                data["currency"] = price.get("Currency", "USD")
                
                if saving_basis := offers[0].get("SavingBasis", {}):
                    data["original_price"] = float(saving_basis.get("Amount", 0))

            # Extract image URL
            if image := item.get("Images", {}).get("Primary", {}).get("Large", {}):
                data["image_url"] = image.get("URL")

            # Extract description/features
            if features := item.get("ItemInfo", {}).get("Features", {}).get("DisplayValues", []):
                data["description"] = "\n".join(features)

            # Validate required fields
            if not all(k in data for k in ["title", "price", "url"]):
                raise InvalidDealDataError(
                    message="Missing required product data",
                    details={
                        "asin": asin,
                        "available_fields": list(data.keys())
                    }
                )

            return data

        except (MarketConnectionError, MarketRateLimitError, MarketAuthenticationError):
            # On API failure, try web scraping as fallback
            logger.warning(f"Amazon API failed, falling back to web scraping for ASIN: {asin}")
            url = f"https://{self.marketplace}/dp/{asin}"
            async with self.web_crawler as crawler:
                return await crawler.extract_product_data(url)

    async def search_products(
        self,
        keywords: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "Featured"
    ) -> List[Dict[str, Any]]:
        """Search for products.
        
        Args:
            keywords: Search keywords
            category: Product category
            min_price: Minimum price filter
            max_price: Maximum price filter
            sort_by: Sort order (Featured, Price, Rating)
            
        Returns:
            List of product data dictionaries
        """
        payload = {
            "Keywords": keywords,
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.marketplace,
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Images.Primary.Large"
            ],
            "SearchIndex": category or "All",
            "SortBy": sort_by
        }

        if min_price is not None:
            payload["MinPrice"] = str(min_price)
        if max_price is not None:
            payload["MaxPrice"] = str(max_price)

        response = await self._make_request("SearchItems", payload)
        
        if "SearchResult" not in response:
            return []

        items = response["SearchResult"].get("Items", [])
        results = []

        for item in items:
            try:
                # Get full product details for each search result
                product = await self.get_product(item["ASIN"])
                results.append(product)
            except Exception as e:
                logger.warning(f"Failed to get details for ASIN {item['ASIN']}: {e}")
                continue

        return results 
