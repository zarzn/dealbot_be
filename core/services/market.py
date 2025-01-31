from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status

from ..repositories.market import MarketRepository
from ..models.market import MarketCreate, MarketUpdate, Market, MarketType, MarketStatus
from ..exceptions import NotFoundException, ValidationError

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