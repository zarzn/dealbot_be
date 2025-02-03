from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.market import MarketType
from ..exceptions import IntegrationError
from decimal import Decimal

class BaseMarketIntegration(ABC):
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
        self._validate_credentials()
        self._initialize_client()

    @abstractmethod
    def _validate_credentials(self) -> None:
        """Validate the provided credentials"""
        pass

    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize the API client"""
        pass

    @abstractmethod
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for products in the marketplace"""
        pass

    @abstractmethod
    async def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific product"""
        pass

    @abstractmethod
    async def get_product_price_history(self, product_id: str) -> List[Dict[str, Any]]:
        """Get price history for a specific product"""
        pass

    @abstractmethod
    async def check_product_availability(self, product_id: str) -> bool:
        """Check if a product is currently available"""
        pass

    def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle and standardize error responses"""
        error_message = f"Error during {operation}: {str(error)}"
        raise IntegrationError(error_message)

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