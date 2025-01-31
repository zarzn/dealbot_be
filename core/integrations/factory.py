from typing import Dict, Optional
from .base import BaseMarketIntegration
from .amazon import AmazonIntegration
from .walmart import WalmartIntegration
from ..models.market import MarketType
from ..exceptions import ValidationError

class MarketIntegrationFactory:
    _integrations: Dict[MarketType, BaseMarketIntegration] = {}

    @classmethod
    def get_integration(cls, market_type: MarketType, credentials: Dict[str, str]) -> BaseMarketIntegration:
        """Get or create a market integration instance"""
        if market_type not in cls._integrations:
            cls._integrations[market_type] = cls._create_integration(market_type, credentials)
        return cls._integrations[market_type]

    @staticmethod
    def _create_integration(market_type: MarketType, credentials: Dict[str, str]) -> BaseMarketIntegration:
        """Create a new market integration instance"""
        if market_type == MarketType.AMAZON:
            return AmazonIntegration(credentials)
        elif market_type == MarketType.WALMART:
            return WalmartIntegration(credentials)
        else:
            raise ValidationError(f"Unsupported market type: {market_type}")

    @classmethod
    def clear_integration(cls, market_type: MarketType) -> None:
        """Remove a market integration instance"""
        if market_type in cls._integrations:
            del cls._integrations[market_type] 