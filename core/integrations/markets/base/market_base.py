"""Enhanced market integration base module."""

from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio
from aiohttp import ClientSession, ClientTimeout
from tenacity import retry, stop_after_attempt, wait_exponential

from core.exceptions import (
    MarketIntegrationError,
    APIError,
    ValidationError,
    RateLimitError
)
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector
from core.config import settings

logger = get_logger(__name__)

class MarketCredentials(Protocol):
    """Protocol for market credentials."""
    api_key: str
    api_secret: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]

class MarketBase(ABC):
    """Enhanced base class for market integrations."""
    
    def __init__(
        self,
        credentials: MarketCredentials,
        session: Optional[ClientSession] = None,
        timeout: int = 30
    ):
        self.credentials = credentials
        self.session = session or ClientSession(
            timeout=ClientTimeout(total=timeout)
        )
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.session:
            self.session = ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for products in the market."""
        pass
        
    @abstractmethod
    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get detailed product information."""
        pass
        
    @abstractmethod
    async def track_price(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Track product price in real-time."""
        pass
        
    @abstractmethod
    async def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a product."""
        pass
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic and rate limiting."""
        try:
            # Check rate limits
            await self._check_rate_limits()
            
            # Prepare headers
            request_headers = {
                'User-Agent': settings.USER_AGENT,
                'Accept': 'application/json',
                **self._get_auth_headers(),
                **(headers or {})
            }
            
            # Make request
            async with self.session.request(
                method,
                url,
                params=params,
                json=data,
                headers=request_headers
            ) as response:
                # Update rate limits
                self._update_rate_limits(response)
                
                # Handle response
                if response.status == 429:
                    raise RateLimitError(
                        f"Rate limit exceeded for {self.__class__.__name__}"
                    )
                    
                response.raise_for_status()
                return await response.json()
                
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(
                f"Request failed for {self.__class__.__name__}: {str(e)}",
                exc_info=True
            )
            raise MarketIntegrationError(f"Request failed: {str(e)}")
            
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for the market."""
        pass
        
    async def _check_rate_limits(self):
        """Check if we're within rate limits."""
        if self.rate_limit_remaining is not None:
            if self.rate_limit_remaining <= 0:
                wait_time = max(
                    0,
                    self.rate_limit_reset - datetime.utcnow().timestamp()
                )
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit reached, waiting {wait_time} seconds"
                    )
                    await asyncio.sleep(wait_time)
                    
    def _update_rate_limits(self, response):
        """Update rate limit information from response headers."""
        try:
            self.rate_limit_remaining = int(
                response.headers.get('X-RateLimit-Remaining', 0)
            )
            self.rate_limit_reset = int(
                response.headers.get('X-RateLimit-Reset', 0)
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Error updating rate limits: {str(e)}")
            
    async def validate_product(
        self,
        product_data: Dict[str, Any]
    ) -> bool:
        """Validate product data."""
        try:
            required_fields = {'id', 'title', 'price', 'url'}
            if not all(field in product_data for field in required_fields):
                return False
                
            # Validate price
            price = float(product_data['price'])
            if price <= 0:
                return False
                
            # Validate URL
            url = product_data['url']
            if not url.startswith(('http://', 'https://')):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Product validation error: {str(e)}")
            return False
            
    async def check_availability(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Check product availability."""
        try:
            details = await self.get_product_details(product_id)
            
            return {
                'available': details.get('in_stock', False),
                'stock_level': details.get('stock_level'),
                'shipping_days': details.get('shipping_days'),
                'seller': details.get('seller'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Availability check error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to check availability: {str(e)}"
            )
            
    @abstractmethod
    async def subscribe_to_changes(
        self,
        product_id: str,
        callback: callable
    ):
        """Subscribe to real-time product changes."""
        pass
        
    @abstractmethod
    async def unsubscribe_from_changes(
        self,
        product_id: str
    ):
        """Unsubscribe from real-time product changes."""
        pass 