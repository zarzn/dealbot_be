from typing import Dict, Optional
from core.integrations.base import MarketBase
from core.integrations.amazon import AmazonIntegration
from core.integrations.walmart import WalmartIntegration
from core.integrations.google_shopping import GoogleShoppingIntegration
from core.models.enums import MarketType
from core.exceptions import BaseError, ValidationError
import logging

logger = logging.getLogger(__name__)

class MarketIntegrationFactory:
    _integrations: Dict[MarketType, MarketBase] = {}

    @classmethod
    def get_integration(cls, market_type: MarketType, credentials: Dict[str, str]) -> MarketBase:
        """Get or create a market integration instance"""
        if market_type not in cls._integrations:
            cls._integrations[market_type] = cls.create_integration(market_type, credentials)
        return cls._integrations[market_type]

    @classmethod
    def create_integration(cls, market_type: MarketType, credentials: Dict[str, str]) -> MarketBase:
        """Create a new market integration instance"""
        if market_type == MarketType.AMAZON:
            return AmazonIntegration(credentials)
        elif market_type == MarketType.WALMART:
            return WalmartIntegration(credentials)
        elif market_type == MarketType.GOOGLE_SHOPPING:
            return GoogleShoppingIntegration(credentials)
        else:
            raise ValidationError(f"Unsupported market type: {market_type}")

    @classmethod
    async def create_integration_async(cls, market_type: MarketType, credentials: Dict[str, str]) -> MarketBase:
        """Create a new market integration instance asynchronously"""
        return cls.create_integration(market_type, credentials)

    @classmethod
    def clear_integration(cls, market_type: MarketType) -> None:
        """Remove a market integration instance"""
        if market_type in cls._integrations:
            del cls._integrations[market_type] 