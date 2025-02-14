"""ScraperAPI integration service.

This module provides integration with ScraperAPI for web scraping capabilities.
"""

from typing import Optional, Dict, Any, List
import aiohttp
import asyncio
from datetime import datetime
from urllib.parse import urlencode

from core.config import settings
from core.utils.logger import get_logger
from core.exceptions.market import (
    MarketIntegrationError,
    MarketRateLimitError,
    MarketConnectionError,
    ProductNotFoundError
)
from core.utils.redis import RedisClient

logger = get_logger(__name__)

class ScraperAPIService:
    """Service for interacting with ScraperAPI."""
    
    def __init__(
        self,
        api_key: str = "34b092724b61ff18f116305a51ee77e7",
        base_url: str = "http://api.scraperapi.com",
        redis_client: Optional[RedisClient] = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.redis_client = redis_client or RedisClient()
        
        # Configure limits
        self.concurrent_limit = 25  # Startup plan limit
        self.requests_per_second = 3
        self.monthly_limit = 200_000
        
        # Configure timeouts
        self.timeout = aiohttp.ClientTimeout(total=70)  # ScraperAPI recommended timeout
        
        # Semaphore for concurrent requests
        self.semaphore = asyncio.Semaphore(self.concurrent_limit)
        
    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        cache_ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make a request to ScraperAPI with retries and caching."""
        params = params or {}
        params['api_key'] = self.api_key
        
        # Check cache if TTL provided
        if cache_ttl:
            cache_key = f"scraper_api:{url}:{str(params)}"
            cached_response = await self.redis_client.get(cache_key)
            if cached_response:
                return cached_response
        
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        async with session.get(
                            url,
                            params=params,
                            ssl=False  # Required for some proxies
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                
                                # Cache successful response if TTL provided
                                if cache_ttl:
                                    await self.redis_client.set(
                                        cache_key,
                                        result,
                                        expire=cache_ttl
                                    )
                                
                                # Track credit usage
                                await self._track_credit_usage('ecommerce')
                                
                                return result
                                
                            elif response.status == 429:
                                raise MarketRateLimitError(
                                    "ScraperAPI rate limit exceeded",
                                    retry_after=60
                                )
                            else:
                                error_text = await response.text()
                                raise MarketIntegrationError(
                                    f"ScraperAPI request failed: {error_text}",
                                    details={'status': response.status}
                                )
                                
                except asyncio.TimeoutError:
                    if attempt == retries - 1:
                        raise MarketConnectionError(
                            "ScraperAPI request timed out after retries"
                        )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                except Exception as e:
                    if attempt == retries - 1:
                        raise MarketIntegrationError(
                            f"ScraperAPI request failed: {str(e)}"
                        )
                    await asyncio.sleep(2 ** attempt)
    
    async def _track_credit_usage(self, request_type: str = 'ecommerce'):
        """Track API credit usage."""
        credits = 5 if request_type == 'ecommerce' else 1
        date_key = datetime.utcnow().strftime('%Y-%m')
        
        async with self.redis_client.pipeline() as pipe:
            await pipe.incrby(f'scraper_api:credits:{date_key}', credits)
            await pipe.expire(f'scraper_api:credits:{date_key}', 60 * 60 * 24 * 35)  # 35 days
            await pipe.execute()
    
    async def search_amazon_products(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800  # 30 minutes
    ) -> List[Dict[str, Any]]:
        """Search for products on Amazon."""
        try:
            params = {
                'url': f'https://www.amazon.com/s?k={query}&page={page}',
                'autoparse': 'true',
                'country_code': 'us'
            }
            
            result = await self._make_request(
                f"{self.base_url}/structured/amazon/search",
                params=params,
                cache_ttl=cache_ttl
            )
            
            if not result.get('results'):
                return []
                
            return result['results']
            
        except Exception as e:
            logger.error(f"Amazon search failed: {str(e)}")
            raise MarketIntegrationError(
                f"Amazon search failed: {str(e)}",
                market="amazon"
            )
    
    async def get_amazon_product(
        self,
        product_id: str,
        cache_ttl: int = 1800  # 30 minutes
    ) -> Dict[str, Any]:
        """Get Amazon product details."""
        try:
            params = {
                'url': f'https://www.amazon.com/dp/{product_id}',
                'autoparse': 'true',
                'country_code': 'us'
            }
            
            result = await self._make_request(
                f"{self.base_url}/structured/amazon/product",
                params=params,
                cache_ttl=cache_ttl
            )
            
            if not result:
                raise ProductNotFoundError(
                    f"Product {product_id} not found on Amazon",
                    market="amazon",
                    product_id=product_id
                )
                
            return result
            
        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Amazon product fetch failed: {str(e)}")
            raise MarketIntegrationError(
                f"Amazon product fetch failed: {str(e)}",
                market="amazon"
            )
    
    async def search_walmart_products(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800  # 30 minutes
    ) -> List[Dict[str, Any]]:
        """Search for products on Walmart."""
        try:
            params = {
                'url': f'https://www.walmart.com/search?q={query}&page={page}',
                'autoparse': 'true',
                'country_code': 'us'
            }
            
            result = await self._make_request(
                f"{self.base_url}/structured/walmart/search",
                params=params,
                cache_ttl=cache_ttl
            )
            
            if not result.get('results'):
                return []
                
            return result['results']
            
        except Exception as e:
            logger.error(f"Walmart search failed: {str(e)}")
            raise MarketIntegrationError(
                f"Walmart search failed: {str(e)}",
                market="walmart"
            )
    
    async def get_walmart_product(
        self,
        product_id: str,
        cache_ttl: int = 1800  # 30 minutes
    ) -> Dict[str, Any]:
        """Get Walmart product details."""
        try:
            params = {
                'url': f'https://www.walmart.com/ip/{product_id}',
                'autoparse': 'true',
                'country_code': 'us'
            }
            
            result = await self._make_request(
                f"{self.base_url}/structured/walmart/product",
                params=params,
                cache_ttl=cache_ttl
            )
            
            if not result:
                raise ProductNotFoundError(
                    f"Product {product_id} not found on Walmart",
                    market="walmart",
                    product_id=product_id
                )
                
            return result
            
        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Walmart product fetch failed: {str(e)}")
            raise MarketIntegrationError(
                f"Walmart product fetch failed: {str(e)}",
                market="walmart"
            )
    
    async def get_credit_usage(self) -> Dict[str, int]:
        """Get current month's credit usage."""
        date_key = datetime.utcnow().strftime('%Y-%m')
        credits_used = await self.redis_client.get(f'scraper_api:credits:{date_key}')
        
        return {
            'credits_used': int(credits_used or 0),
            'credits_remaining': self.monthly_limit - int(credits_used or 0)
        } 