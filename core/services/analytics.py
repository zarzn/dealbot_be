"""Analytics service module.

This module provides analytics services for markets, deals, and user behavior.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.analytics import AnalyticsRepository
from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.models.market import (
    Market,
    MarketAnalytics,
    MarketComparison,
    MarketPriceHistory,
    MarketAvailability,
    MarketTrends,
    MarketPerformance
)
from core.exceptions import (
    ValidationError,
    NotFoundException,
    DatabaseError,
    MarketError,
    AnalyticsError,
    APIError,
    APIServiceUnavailableError,
    CacheOperationError,
    RepositoryError,
    DataProcessingError
)

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for analytics operations."""

    def __init__(
        self,
        analytics_repository: AnalyticsRepository,
        market_repository: Optional[MarketRepository] = None,
        deal_repository: Optional[DealRepository] = None
    ):
        self.analytics_repository = analytics_repository
        self.market_repository = market_repository
        self.deal_repository = deal_repository

    async def get_market_analytics(self, market_id: UUID) -> MarketAnalytics:
        """Get analytics for a specific market."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            analytics_data = await self.analytics_repository.get_market_analytics(market_id)
            if not analytics_data:
                # Generate default analytics if none exist
                analytics_data = {
                    "total_products": 0,
                    "active_deals": 0,
                    "average_discount": 0.0,
                    "top_categories": [],
                    "price_ranges": {},
                    "daily_stats": {
                        "new_deals": 0,
                        "expired_deals": 0,
                        "price_drops": 0
                    }
                }

            return MarketAnalytics(**analytics_data)
        except Exception as e:
            logger.error(f"Error getting market analytics: {str(e)}")
            raise MarketError(f"Failed to get market analytics: {str(e)}")

    async def get_market_comparison(
        self,
        market_ids: List[UUID],
        metrics: Optional[List[str]] = None
    ) -> MarketComparison:
        """Compare multiple markets."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            markets = []
            for market_id in market_ids:
                market = await self.market_repository.get_by_id(market_id)
                if not market:
                    raise NotFoundException(f"Market with id {market_id} not found")
                markets.append(market)

            comparison_data = await self.analytics_repository.get_market_comparison(
                market_ids,
                metrics
            )

            return MarketComparison(**comparison_data)
        except Exception as e:
            logger.error(f"Error comparing markets: {str(e)}")
            raise MarketError(f"Failed to compare markets: {str(e)}")

    async def get_market_price_history(
        self,
        market_id: UUID,
        product_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> MarketPriceHistory:
        """Get price history for a product in a market."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            history_data = await self.analytics_repository.get_price_history(
                market_id,
                product_id,
                start_date,
                end_date
            )

            return MarketPriceHistory(**history_data)
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise MarketError(f"Failed to get price history: {str(e)}")

    async def get_market_availability(self, market_id: UUID) -> MarketAvailability:
        """Get availability metrics for a market."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            availability_data = await self.analytics_repository.get_market_availability(market_id)

            return MarketAvailability(**availability_data)
        except Exception as e:
            logger.error(f"Error getting market availability: {str(e)}")
            raise MarketError(f"Failed to get market availability: {str(e)}")

    async def get_market_trends(
        self,
        market_id: UUID,
        trend_period: str = "24h"
    ) -> MarketTrends:
        """Get market trends."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            trends_data = await self.analytics_repository.get_market_trends(
                market_id,
                trend_period
            )

            return MarketTrends(**trends_data)
        except Exception as e:
            logger.error(f"Error getting market trends: {str(e)}")
            raise MarketError(f"Failed to get market trends: {str(e)}")

    async def get_market_performance(self, market_id: UUID) -> MarketPerformance:
        """Get market performance metrics."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            performance_data = await self.analytics_repository.get_market_performance(market_id)

            return MarketPerformance(**performance_data)
        except Exception as e:
            logger.error(f"Error getting market performance: {str(e)}")
            raise MarketError(f"Failed to get market performance: {str(e)}")

    async def update_market_analytics(
        self,
        market_id: UUID,
        analytics_data: Dict[str, Any]
    ) -> None:
        """Update analytics data for a market."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            await self.analytics_repository.update_market_analytics(
                market_id,
                analytics_data
            )
        except Exception as e:
            logger.error(f"Error updating market analytics: {str(e)}")
            raise MarketError(f"Failed to update market analytics: {str(e)}")

    async def aggregate_market_stats(self, market_id: UUID) -> None:
        """Aggregate market statistics."""
        try:
            if not self.market_repository:
                raise ValidationError("Market repository not initialized")

            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise NotFoundException(f"Market with id {market_id} not found")

            await self.analytics_repository.aggregate_market_stats(market_id)
        except Exception as e:
            logger.error(f"Error aggregating market stats: {str(e)}")
            raise MarketError(f"Failed to aggregate market stats: {str(e)}") 
