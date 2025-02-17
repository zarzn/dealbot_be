"""Mock market integration for testing."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import random
import asyncio
from uuid import uuid4

from backend.core.integrations.markets.base.market_base import MarketBase, MarketCredentials
from backend.core.exceptions.market_exceptions import MarketIntegrationError, ProductNotFoundError

class MockMarketCredentials(MarketCredentials):
    """Mock market credentials for testing."""
    api_key: str = "mock_api_key"
    api_secret: Optional[str] = "mock_api_secret"
    region: str = "US"

class MockMarketIntegration(MarketBase):
    """Mock market integration for testing."""

    def __init__(self, credentials: MockMarketCredentials):
        super().__init__(credentials)
        self._products: Dict[str, Dict[str, Any]] = {}
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}
        self._subscribers: Dict[str, List[callable]] = {}
        self._mock_delay = 0.1  # Simulated network delay

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Mock product search."""
        await asyncio.sleep(self._mock_delay)
        
        # Generate mock products
        products = []
        for _ in range(min(limit, 5)):
            product_id = str(uuid4())
            price = random.uniform(min_price or 10, max_price or 1000)
            product = {
                "id": product_id,
                "title": f"Mock Product for {query}",
                "description": f"Mock description for {query}",
                "price": Decimal(str(round(price, 2))),
                "currency": "USD",
                "category": category or "General",
                "url": f"https://mock-market.com/products/{product_id}",
                "image_url": f"https://mock-market.com/images/{product_id}.jpg",
                "availability": True,
                "rating": random.uniform(3.0, 5.0),
                "review_count": random.randint(10, 1000),
                "seller": "Mock Seller",
                "seller_rating": random.uniform(4.0, 5.0),
                "metadata": {
                    "source": "mock_market",
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            self._products[product_id] = product
            products.append(product)
            
        return products

    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Mock get product details."""
        await asyncio.sleep(self._mock_delay)
        
        if product_id not in self._products:
            raise ProductNotFoundError(f"Product {product_id} not found")
            
        return self._products[product_id]

    async def track_price(
        self,
        product_id: str,
        check_interval: int = 300
    ) -> Dict[str, Any]:
        """Mock price tracking."""
        await asyncio.sleep(self._mock_delay)
        
        if product_id not in self._products:
            raise ProductNotFoundError(f"Product {product_id} not found")
            
        # Initialize price history if not exists
        if product_id not in self._price_history:
            self._price_history[product_id] = []
            
        current_price = self._products[product_id]["price"]
        timestamp = datetime.utcnow()
        
        price_point = {
            "price": current_price,
            "currency": "USD",
            "timestamp": timestamp.isoformat(),
            "source": "mock_market"
        }
        
        self._price_history[product_id].append(price_point)
        
        return {
            "product_id": product_id,
            "current_price": current_price,
            "currency": "USD",
            "tracking_id": str(uuid4()),
            "check_interval": check_interval,
            "last_checked": timestamp.isoformat(),
            "status": "active"
        }

    async def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Mock get price history."""
        await asyncio.sleep(self._mock_delay)
        
        if product_id not in self._products:
            raise ProductNotFoundError(f"Product {product_id} not found")
            
        # Generate mock price history if not exists
        if product_id not in self._price_history:
            self._price_history[product_id] = []
            base_price = float(self._products[product_id]["price"])
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            current_date = start_date
            while current_date <= end_date:
                # Add some random price variation
                variation = random.uniform(-0.1, 0.1)  # ±10%
                price = Decimal(str(round(base_price * (1 + variation), 2)))
                
                price_point = {
                    "price": price,
                    "currency": "USD",
                    "timestamp": current_date.isoformat(),
                    "source": "mock_market"
                }
                self._price_history[product_id].append(price_point)
                current_date += timedelta(hours=random.randint(1, 24))
                
        return self._price_history[product_id]

    async def subscribe_to_changes(
        self,
        product_id: str,
        callback: callable
    ):
        """Mock subscribe to product changes."""
        if product_id not in self._subscribers:
            self._subscribers[product_id] = []
        self._subscribers[product_id].append(callback)

    async def unsubscribe_from_changes(
        self,
        product_id: str
    ):
        """Mock unsubscribe from product changes."""
        if product_id in self._subscribers:
            self._subscribers.pop(product_id)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Mock get authentication headers."""
        return {
            "Authorization": f"Bearer {self._credentials.api_key}",
            "Market-Secret": self._credentials.api_secret or "",
            "Market-Region": self._credentials.region
        }

    async def simulate_price_change(
        self,
        product_id: str,
        new_price: Decimal
    ):
        """Simulate a price change for testing."""
        if product_id not in self._products:
            raise ProductNotFoundError(f"Product {product_id} not found")
            
        old_price = self._products[product_id]["price"]
        self._products[product_id]["price"] = new_price
        
        # Add to price history
        price_point = {
            "price": new_price,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "mock_market"
        }
        self._price_history[product_id].append(price_point)
        
        # Notify subscribers
        if product_id in self._subscribers:
            change_data = {
                "product_id": product_id,
                "old_price": old_price,
                "new_price": new_price,
                "currency": "USD",
                "timestamp": datetime.utcnow().isoformat()
            }
            for callback in self._subscribers[product_id]:
                await callback(change_data) 