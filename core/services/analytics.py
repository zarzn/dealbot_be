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
from core.models.deal import AIAnalysis
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

    async def get_deal_analysis(
        self, 
        deal_id: UUID, 
        user_id: Optional[UUID] = None,
        deal_analysis_service = None
    ) -> AIAnalysis:
        """
        Get analysis for a specific deal.
        
        This method can be used by both authenticated and unauthenticated users.
        Unauthenticated users will receive a simplified analysis.
        
        Args:
            deal_id: The UUID of the deal to analyze
            user_id: Optional user ID for authenticated users
            deal_analysis_service: Optional DealAnalysisService instance
            
        Returns:
            AIAnalysis object with deal analysis
            
        Raises:
            NotFoundException: If the deal is not found
            AnalyticsError: If analysis fails
        """
        try:
            if not self.deal_repository:
                raise ValidationError("Deal repository not initialized")
                
            # Check cache first
            cached_analysis = await self.analytics_repository.get_deal_analysis(deal_id)
            if cached_analysis:
                return AIAnalysis(**cached_analysis)
                
            # Get the deal
            deal = await self.deal_repository.get_by_id(deal_id)
            if not deal:
                raise NotFoundException(f"Deal with id {deal_id} not found")
                
            # For unauthenticated users, generate simplified analysis
            if user_id is None:
                if not deal_analysis_service:
                    raise ValidationError("Deal analysis service required for unauthenticated analysis")
                    
                analysis = await deal_analysis_service.generate_simplified_analysis(deal)
                
                # Cache the simplified analysis
                await self.analytics_repository.save_deal_analysis(
                    deal_id=deal_id,
                    analysis_data=analysis.dict(),
                    ttl=3600  # 1 hour cache
                )
                
                return analysis
                
            # For authenticated users, generate detailed analysis
            # This would typically call the full analysis service
            # For now, we'll generate a more detailed mock analysis
            
            # Calculate discount percentage
            original_price = deal.original_price or deal.price
            discount_percentage = 0
            if original_price > 0:
                discount_percentage = ((original_price - deal.price) / original_price) * 100
                
            # Calculate score based on multiple factors
            base_score = min(discount_percentage / 40, 1.0)  # 40% discount = score of 1.0
            
            # Adjust score based on seller rating if available
            seller_rating = deal.seller_info.get("rating", 0) if deal.seller_info else 0
            seller_adjustment = (seller_rating / 5) * 0.2  # Up to 0.2 points for perfect rating
            
            # Adjust score based on price history if available
            price_trend_adjustment = 0
            if hasattr(deal, 'price_points') and deal.price_points:
                # Simple trend detection
                prices = [point.price for point in deal.price_points]
                if len(prices) > 1:
                    if prices[-1] < prices[0]:  # Price is decreasing
                        price_trend_adjustment = 0.1
                    elif prices[-1] > prices[0]:  # Price is increasing
                        price_trend_adjustment = -0.1
            
            # Final score calculation
            score = base_score + seller_adjustment + price_trend_adjustment
            score = max(0, min(score, 1.0))  # Ensure score is between 0 and 1
            
            # Generate recommendations
            recommendations = []
            
            # Deal expiration recommendation
            if deal.expires_at:
                days_until_expiry = (deal.expires_at - datetime.utcnow()).days
                if days_until_expiry < 3:
                    recommendations.append(f"Deal expires in {days_until_expiry} days - act quickly.")
                elif days_until_expiry < 7:
                    recommendations.append(f"Deal expires in {days_until_expiry} days - consider soon.")
            
            # Discount-based recommendation
            if discount_percentage > 40:
                recommendations.append(f"Exceptional discount of {discount_percentage:.1f}% off original price.")
            elif discount_percentage > 20:
                recommendations.append(f"Good discount of {discount_percentage:.1f}% off original price.")
            elif discount_percentage > 10:
                recommendations.append(f"Moderate discount of {discount_percentage:.1f}% off original price.")
            
            # Price trend recommendation
            if price_trend_adjustment > 0:
                recommendations.append("Price has been decreasing - good time to buy.")
            elif price_trend_adjustment < 0:
                recommendations.append("Price has been increasing - may continue to rise.")
            
            # Add generic recommendation if we don't have enough
            if len(recommendations) < 3:
                recommendations.append("Compare with similar products before purchasing.")
            
            # Create analysis result
            analysis = AIAnalysis(
                deal_id=deal.id,
                score=float(score),
                confidence=0.85,  # Higher confidence for authenticated users
                price_analysis={
                    "discount_percentage": float(discount_percentage),
                    "is_good_deal": score > 0.7,
                    "price_trend": "decreasing" if price_trend_adjustment > 0 else "increasing" if price_trend_adjustment < 0 else "stable"
                },
                market_analysis={
                    "competition": "High" if hasattr(deal, 'market_analysis') and deal.market_analysis and deal.market_analysis.get("competition_level") == "high" else "Medium",
                    "availability": "Available" if deal.is_available else "Limited"
                },
                recommendations=recommendations[:3],  # Limit to top 3 recommendations
                analysis_date=datetime.utcnow(),
                expiration_analysis="Expires soon" if deal.expires_at and (deal.expires_at - datetime.utcnow()).days < 3 else "No immediate expiration"
            )
            
            # Cache the analysis
            await self.analytics_repository.save_deal_analysis(
                deal_id=deal_id,
                analysis_data=analysis.dict(),
                ttl=3600  # 1 hour cache
            )
            
            return analysis
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting deal analysis: {str(e)}")
            raise AnalyticsError(f"Failed to get deal analysis: {str(e)}") 