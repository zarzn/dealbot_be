"""Web crawler utility for scraping product data.

This module provides a robust web crawler implementation for extracting product
information from various e-commerce websites when API access is not available
or as a fallback mechanism.
"""

import asyncio
from datetime import datetime
import json
from typing import Dict, List, Optional, Any
import aiohttp
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse

from ..exceptions import (
    MarketConnectionError,
    MarketRateLimitError,
    InvalidDealDataError
)
from ..config import settings

logger = logging.getLogger(__name__)

class WebCrawler:
    """Asynchronous web crawler for e-commerce sites."""

    def __init__(
        self,
        max_retries: int = 3,
        timeout: int = 30,
        rate_limit: float = 1.0,
        user_agent: Optional[str] = None
    ):
        """Initialize the web crawler.
        
        Args:
            max_retries: Maximum number of retry attempts for failed requests
            timeout: Request timeout in seconds
            rate_limit: Minimum time between requests in seconds
            user_agent: Custom user agent string
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.last_request_time: Dict[str, datetime] = {}
        
        self.headers = {
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Create aiohttp session on context manager enter."""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session on context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _enforce_rate_limit(self, domain: str) -> None:
        """Enforce rate limiting for each domain.
        
        Args:
            domain: The domain to enforce rate limiting for
        """
        if domain in self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time[domain]).total_seconds()
            if elapsed < self.rate_limit:
                await asyncio.sleep(self.rate_limit - elapsed)
        self.last_request_time[domain] = datetime.now()

    async def get_page(self, url: str, retry_count: int = 0) -> str:
        """Fetch a page with retry logic and rate limiting.
        
        Args:
            url: The URL to fetch
            retry_count: Current retry attempt number
            
        Returns:
            The page HTML content
            
        Raises:
            MarketConnectionError: If connection fails after all retries
            MarketRateLimitError: If rate limit is detected
        """
        if not self.session:
            raise RuntimeError("WebCrawler must be used as a context manager")

        domain = urlparse(url).netloc
        await self._enforce_rate_limit(domain)

        try:
            async with self.session.get(url, timeout=self.timeout) as response:
                if response.status == 429:
                    raise MarketRateLimitError(
                        market=domain,
                        message=f"Rate limit exceeded for {domain}"
                    )
                    
                if response.status >= 400:
                    if retry_count < self.max_retries:
                        await asyncio.sleep(2 ** retry_count)
                        return await self.get_page(url, retry_count + 1)
                    raise MarketConnectionError(
                        market=domain,
                        message=f"Failed to fetch page: {response.status}"
                    )
                
                return await response.text()

        except asyncio.TimeoutError:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self.get_page(url, retry_count + 1)
            raise MarketConnectionError(
                market=domain,
                message="Request timed out"
            )

        except Exception as e:
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self.get_page(url, retry_count + 1)
            raise MarketConnectionError(
                market=domain,
                message=str(e)
            )

    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text.
        
        Args:
            text: Text containing a price
            
        Returns:
            Extracted price as float or None if no valid price found
        """
        try:
            # Remove currency symbols and other non-numeric characters
            cleaned = ''.join(c for c in text if c.isdigit() or c == '.')
            # Handle cases with multiple dots
            parts = cleaned.split('.')
            if len(parts) > 2:
                cleaned = parts[0] + '.' + ''.join(parts[1:])
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    async def extract_product_data(self, url: str) -> Dict[str, Any]:
        """Extract product information from a product page.
        
        Args:
            url: Product page URL
            
        Returns:
            Dictionary containing extracted product data
            
        Raises:
            InvalidDealDataError: If required product data cannot be extracted
        """
        html = await self.get_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        data = {
            'url': url,
            'source': urlparse(url).netloc,
            'crawled_at': datetime.now().isoformat()
        }

        # Extract title
        title_selectors = [
            'h1[itemprop="name"]',
            'h1.product-title',
            '#productTitle',
            '.product-name h1'
        ]
        for selector in title_selectors:
            if title_elem := soup.select_one(selector):
                data['title'] = title_elem.get_text().strip()
                break

        # Extract price
        price_selectors = [
            'span[itemprop="price"]',
            '.product-price',
            '#priceblock_ourprice',
            '.price-box .price'
        ]
        for selector in price_selectors:
            if price_elem := soup.select_one(selector):
                if price := self._extract_price(price_elem.get_text()):
                    data['price'] = price
                    break

        # Extract original price
        original_price_selectors = [
            'span[itemprop="originalPrice"]',
            '.original-price',
            '#priceblock_listprice',
            '.old-price .price'
        ]
        for selector in original_price_selectors:
            if orig_price_elem := soup.select_one(selector):
                if orig_price := self._extract_price(orig_price_elem.get_text()):
                    data['original_price'] = orig_price
                    break

        # Extract image URL
        image_selectors = [
            'img[itemprop="image"]',
            '#landingImage',
            '.product-image-photo'
        ]
        for selector in image_selectors:
            if img_elem := soup.select_one(selector):
                img_url = img_elem.get('src') or img_elem.get('data-src')
                if img_url:
                    data['image_url'] = urljoin(url, img_url)
                    break

        # Extract description
        description_selectors = [
            'div[itemprop="description"]',
            '#productDescription',
            '.product-info-main .description'
        ]
        for selector in description_selectors:
            if desc_elem := soup.select_one(selector):
                data['description'] = desc_elem.get_text().strip()
                break

        # Validate required fields
        if not all(k in data for k in ['title', 'price']):
            raise InvalidDealDataError(
                message="Failed to extract required product data",
                details={
                    'url': url,
                    'extracted_fields': list(data.keys())
                }
            )

        return data

    async def search_products(self, query: str, market_url: str) -> List[Dict[str, Any]]:
        """Search for products on a given marketplace.
        
        Args:
            query: Search query
            market_url: Base URL of the marketplace
            
        Returns:
            List of product data dictionaries
        """
        # Implement market-specific search logic here
        # This is a placeholder that should be implemented based on specific market requirements
        raise NotImplementedError("Search functionality must be implemented per market") 