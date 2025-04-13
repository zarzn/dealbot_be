"""Market-specific Oxylabs services."""

from core.integrations.oxylabs.market_base import OxylabsMarketBaseService
from core.integrations.oxylabs.markets.amazon import AmazonOxylabsService
from core.integrations.oxylabs.markets.walmart import WalmartOxylabsService
from core.integrations.oxylabs.markets.google_shopping import GoogleShoppingOxylabsService
from core.integrations.oxylabs.markets.ebay import EbayOxylabsService

__all__ = [
    "OxylabsMarketBaseService",
    "AmazonOxylabsService",
    "WalmartOxylabsService",
    "GoogleShoppingOxylabsService",
    "EbayOxylabsService",
] 