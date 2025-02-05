from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status

from ..repositories.market import MarketRepository
from ..models.market import MarketCreate, MarketUpdate, Market, MarketType, MarketStatus
from ..exceptions import (
    NotFoundException,
    ValidationError,
    MarketError,
    MarketNotFoundError,
    MarketValidationError,
    MarketConnectionError,
    MarketRateLimitError,
    MarketConfigurationError,
    MarketOperationError,
    APIError,
    APIAuthenticationError,
    APIServiceUnavailableError,
    DatabaseError,
    CacheOperationError,
    RepositoryError,
    NetworkError,
    DataProcessingError
)


class MarketService:
    def __init__(self, market_repository: MarketRepository):
        self.market_repository = market_repository

    async def create_market(self, market_data: MarketCreate) -> Market:
        # Check if market with same type already exists
        existing_market = await self.market_repository.get_by_type(market_data.type)
        if existing_market:
            raise ValidationError(f"Market with type {market_data.type} already exists")

        # Validate API credentials if provided
        if market_data.api_credentials:
            self._validate_api_credentials(market_data.type, market_data.api_credentials)

        return await self.market_repository.create(market_data)

    async def get_market(self, market_id: UUID) -> Market:
        market = await self.market_repository.get_by_id(market_id)
        if not market:
            raise NotFoundException(f"Market with id {market_id} not found")
        return market

    async def get_market_by_type(self, market_type: MarketType) -> Market:
        market = await self.market_repository.get_by_type(market_type)
        if not market:
            raise NotFoundException(f"Market of type {market_type} not found")
        return market

    async def get_all_markets(self) -> List[Market]:
        return await self.market_repository.get_all()

    async def get_active_markets(self) -> List[Market]:
        return await self.market_repository.get_all_active()

    async def update_market(self, market_id: UUID, market_data: MarketUpdate) -> Market:
        market = await self.get_market(market_id)

        # Validate API credentials if provided
        if market_data.api_credentials:
            self._validate_api_credentials(market.type, market_data.api_credentials)

        updated_market = await self.market_repository.update(market_id, market_data)
        if not updated_market:
            raise NotFoundException(f"Market with id {market_id} not found")
        return updated_market

    async def delete_market(self, market_id: UUID) -> bool:
        market = await self.get_market(market_id)
        return await self.market_repository.delete(market_id)

    def _validate_api_credentials(self, market_type: MarketType, credentials: dict) -> None:
        """Validate market-specific API credentials"""
        required_fields = {
            MarketType.AMAZON: ["access_key", "secret_key", "partner_tag"],
            MarketType.WALMART: ["client_id", "client_secret"],
            MarketType.EBAY: ["app_id", "cert_id", "dev_id"]
        }

        if market_type not in required_fields:
            raise ValidationError(f"Unsupported market type: {market_type}")

        missing_fields = [field for field in required_fields[market_type] 
                         if field not in credentials]
        
        if missing_fields:
            raise ValidationError(
                f"Missing required API credentials for {market_type}: {', '.join(missing_fields)}"
            )

    async def get_categories(self, market_id: UUID) -> List[dict]:
        """Get categories for a specific market"""
        market = await self.get_market(market_id)
        
        # Default categories for supported markets
        default_categories = {
            MarketType.AMAZON: [
                {"id": "electronics", "name": "Electronics", "parent_id": None},
                {"id": "computers", "name": "Computers", "parent_id": "electronics"},
                {"id": "phones", "name": "Phones & Accessories", "parent_id": "electronics"},
                {"id": "home", "name": "Home & Kitchen", "parent_id": None},
                {"id": "appliances", "name": "Appliances", "parent_id": "home"}
            ],
            MarketType.WALMART: [
                {"id": "electronics", "name": "Electronics", "parent_id": None},
                {"id": "home", "name": "Home", "parent_id": None},
                {"id": "grocery", "name": "Grocery", "parent_id": None}
            ]
        }
        
        try:
            if market.type in default_categories:
                return default_categories[market.type]
            else:
                raise ValidationError(f"Categories not available for market type: {market.type}")
        except Exception as e:
            raise ValidationError(f"Error fetching categories: {str(e)}")

    async def get_market_analytics(self, market_id: UUID) -> dict:
        """Get analytics for a specific market"""
        market = await self.get_market(market_id)
        
        try:
            # In a real implementation, this would fetch actual analytics data
            # For now, returning mock data
            return {
                "total_products": 1000000,
                "active_deals": 5000,
                "average_discount": 25.5,
                "top_categories": [
                    {"name": "Electronics", "deal_count": 1500},
                    {"name": "Home & Kitchen", "deal_count": 1200},
                    {"name": "Fashion", "deal_count": 800}
                ],
                "price_ranges": {
                    "0-50": 2000,
                    "51-100": 1500,
                    "101-500": 1000,
                    "500+": 500
                },
                "daily_stats": {
                    "new_deals": 250,
                    "expired_deals": 200,
                    "price_drops": 300
                }
            }
        except Exception as e:
            raise ValidationError(f"Error fetching market analytics: {str(e)}")

    async def get_market_comparison(self, market_ids: List[UUID]) -> dict:
        """Compare multiple markets"""
        markets = []
        for market_id in market_ids:
            market = await self.get_market(market_id)
            markets.append(market)
        
        try:
            # In a real implementation, this would fetch actual comparison data
            # For now, returning mock data
            return {
                "comparison_date": "2024-02-03",
                "markets": [
                    {
                        "id": str(market.id),
                        "name": market.name,
                        "type": market.type.value,
                        "metrics": {
                            "total_products": 1000000,
                            "active_deals": 5000,
                            "average_discount": 25.5,
                            "response_time": "120ms",
                            "success_rate": 99.5
                        }
                    }
                    for market in markets
                ],
                "summary": {
                    "best_prices": markets[0].name if markets else None,
                    "most_deals": markets[-1].name if markets else None,
                    "fastest_updates": markets[0].name if markets else None
                }
            }
        except Exception as e:
            raise ValidationError(f"Error comparing markets: {str(e)}") 
