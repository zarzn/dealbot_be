"""Enhanced market integration base module."""

from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import asyncio
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from core.utils.logger import get_logger
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    MarketRateLimitError,
    ProductNotFoundError
)
from core.models.deal import Deal
from core.utils.metrics import MetricsCollector

logger = get_logger(__name__)

class MarketCredentials(Protocol):
    """Protocol for market integration credentials."""
    api_key: str
    api_secret: Optional[str]
    region: Optional[str]

class MarketBase(ABC):
    """Base class for market integrations."""
    
    def __init__(
        self,
        credentials: MarketCredentials,
        session: Optional[aiohttp.ClientSession] = None,
        rate_limit_calls: int = 100,
        rate_limit_period: int = 60,
        max_retries: int = 3,
        retry_delay: int = 1
    ):
        self.credentials = credentials
        self._session = session
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._call_count = 0
        self._last_reset = datetime.utcnow()
        self._rate_limit_lock = asyncio.Lock()
        self._metrics = MetricsCollector()
        
    async def __aenter__(self):
        """Async context manager entry."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            
    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for products in the market."""
        pass
        
    @abstractmethod
    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get detailed information about a product."""
        pass
        
    @abstractmethod
    async def track_price(
        self,
        product_id: str,
        check_interval: int = 300
    ) -> Dict[str, Any]:
        """Start tracking price for a product."""
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
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(MarketRateLimitError)
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Make HTTP request with retry capabilities."""
        try:
            # Check rate limits
            await self._check_rate_limit()
            
            start_time = datetime.utcnow()
            
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=timeout
            ) as response:
                # Update metrics
                self._metrics.record_request(
                    market=self.__class__.__name__,
                    method=method,
                    status=response.status,
                    duration=(datetime.utcnow() - start_time).total_seconds()
                )
                
                # Handle rate limits
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(
                        f"Rate limit hit. Waiting {retry_after} seconds"
                    )
                    raise MarketRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after}s"
                    )
                    
                # Handle other errors
                if response.status >= 400:
                    error_data = await response.json()
                    error_msg = error_data.get('message', str(error_data))
                    raise MarketIntegrationError(
                        f"Request failed: {error_msg}"
                    )
                    
                return await response.json()
                
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {url}")
            raise MarketIntegrationError("Request timeout")
            
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            raise MarketIntegrationError(f"Request failed: {str(e)}")
            
    async def _check_rate_limit(self):
        """Check and update rate limit tracking."""
        async with self._rate_limit_lock:
            current_time = datetime.utcnow()
            
            # Reset counter if period has passed
            if (current_time - self._last_reset).total_seconds() >= self.rate_limit_period:
                self._call_count = 0
                self._last_reset = current_time
                
            # Check if limit reached
            if self._call_count >= self.rate_limit_calls:
                wait_time = self.rate_limit_period - (
                    current_time - self._last_reset
                ).total_seconds()
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit reached. Waiting {wait_time:.2f}s"
                    )
                    raise MarketRateLimitError(
                        f"Rate limit reached. Retry after {wait_time:.2f}s"
                    )
                    
            # Increment counter
            self._call_count += 1
            
    async def _validate_product_data(
        self,
        data: Dict[str, Any]
    ) -> bool:
        """Validate product data structure."""
        required_fields = {'id', 'title', 'price', 'url'}
        return all(field in data for field in required_fields)
        
    async def _check_product_availability(
        self,
        product_data: Dict[str, Any]
    ) -> bool:
        """Check if product is available."""
        return (
            product_data.get('in_stock', False) and
            product_data.get('price', 0) > 0
        )
        
    @abstractmethod
    async def subscribe_to_changes(
        self,
        product_id: str,
        callback: callable
    ):
        """Subscribe to product changes."""
        pass
        
    @abstractmethod
    async def unsubscribe_from_changes(
        self,
        product_id: str
    ):
        """Unsubscribe from product changes."""
        pass

    def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle and standardize error responses"""
        error_message = f"Error during {operation}: {str(error)}"
        raise IntegrationError(message=error_message, operation=operation)

    @staticmethod
    def format_product_response(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format raw product data into a standardized response"""
        return {
            "id": raw_data.get("id"),
            "title": raw_data.get("title"),
            "description": raw_data.get("description"),
            "price": raw_data.get("price"),
            "currency": raw_data.get("currency", "USD"),
            "url": raw_data.get("url"),
            "image_url": raw_data.get("image_url"),
            "brand": raw_data.get("brand"),
            "category": raw_data.get("category"),
            "availability": raw_data.get("availability", False),
            "rating": raw_data.get("rating"),
            "review_count": raw_data.get("review_count", 0),
            "marketplace": raw_data.get("marketplace"),
            "seller": raw_data.get("seller"),
            "metadata": raw_data.get("metadata", {})
        }

    def _normalize_deal_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw deal data to standard format"""
        return {
            "title": raw_data["title"],
            "description": raw_data.get("description"),
            "price": Decimal(str(raw_data["price"])),
            "original_price": Decimal(str(raw_data["original_price"])) if raw_data.get("original_price") else None,
            "currency": raw_data.get("currency", "USD"),
            "source": self.source_name,
            "url": raw_data["url"],
            "image_url": raw_data.get("image_url"),
            "deal_metadata": raw_data.get("deal_metadata", {}),
            "price_metadata": raw_data.get("price_metadata", {}),
            "expires_at": raw_data.get("expires_at")
        } 