"""Analytics service module.

This module provides analytics services for markets, deals, and user behavior.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import json
from decimal import Decimal

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
from core.models.deal import AIAnalysis, DealStatus
from core.models.goal import GoalAnalytics
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
    DataProcessingError,
    ServiceError
)

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for analytics operations."""

    def __init__(
        self,
        analytics_repository: AnalyticsRepository,
        market_repository: Optional[MarketRepository] = None,
        deal_repository: Optional[DealRepository] = None,
        goal_service = None
    ):
        self.analytics_repository = analytics_repository
        self.market_repository = market_repository
        self.deal_repository = deal_repository
        self.goal_service = goal_service

    async def get_deal_metrics(
        self,
        user_id: UUID,
        time_range: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics for all deals belonging to a user.
        
        Args:
            user_id: The ID of the user
            time_range: Optional time range for filtering deals (e.g., "24h", "7d", "30d")
            
        Returns:
            Dictionary containing deal metrics
        """
        try:
            # Check if deal repository is initialized
            if not self.deal_repository:
                logger.error("Deal repository not initialized in get_deal_metrics")
                raise ValidationError("Deal repository not initialized")
            
            # Get all deals for the user - wrap this in its own try block for detailed errors
            try:    
                user_deals = await self.deal_repository.get_by_user(user_id=user_id)
                logger.info(f"Retrieved {len(user_deals) if user_deals else 0} deals for user {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving deals for user {user_id}: {str(e)}", exc_info=True)
                raise AnalyticsError(
                    message=f"Failed to retrieve deals: {str(e)}",
                    details={"user_id": str(user_id)}
                )
                
            # Apply time range filter if specified
            if time_range and user_deals:
                try:
                    filtered_deals = []
                    # Use timezone-aware UTC datetime
                    now = datetime.now(timezone.utc)
                    
                    # Convert time_range to timedelta
                    if time_range == "24h":
                        start_time = now - timedelta(hours=24)
                    elif time_range == "7d":
                        start_time = now - timedelta(days=7)
                    elif time_range == "30d":
                        start_time = now - timedelta(days=30)
                    elif time_range == "90d":
                        start_time = now - timedelta(days=90)
                    else:
                        # Invalid time range, use all deals
                        filtered_deals = user_deals
                    
                    # Filter deals by creation time
                    if not filtered_deals:  # Only filter if we haven't set it above
                        filtered_deals = [
                            deal for deal in user_deals 
                            if deal.created_at and self._ensure_timezone_aware(deal.created_at) >= start_time
                        ]
                    
                    user_deals = filtered_deals
                    logger.info(f"Applied time range filter '{time_range}', {len(user_deals)} deals remaining")
                except Exception as e:
                    logger.error(f"Error applying time range filter: {str(e)}", exc_info=True)
                    # Continue with all deals if filter fails
                    logger.warning("Continuing with all deals due to filter error")
            
            # Default response if no deals found
            default_response = {
                "total_deals": 0,
                "total_value": 0,
                "successful_deals": 0,
                "pending_deals": 0,
                "failed_deals": 0,
                "avg_completion_time": 0,
                "most_active_market": None
            }
            
            if not user_deals:
                logger.info(f"No deals found for user {user_id}, returning default metrics")
                return default_response
                
            # Calculate metrics safely
            try:
                # Basic metrics
                total_deals = len(user_deals)
                logger.debug(f"Total deals: {total_deals}")
                
                # Safely calculate total_value with error handling
                total_value = 0
                try:
                    for deal in user_deals:
                        if hasattr(deal, 'price') and deal.price is not None:
                            # Convert Decimal to float for JSON serialization
                            if isinstance(deal.price, Decimal):
                                total_value += float(deal.price)
                            else:
                                total_value += deal.price
                    logger.debug(f"Total value calculated: {total_value}")
                except (TypeError, ValueError, AttributeError) as e:
                    logger.warning(f"Error calculating total_value: {str(e)}")
                
                # Safely count deal statuses
                successful_deals = 0
                pending_deals = 0
                failed_deals = 0
                
                for deal in user_deals:
                    try:
                        if hasattr(deal, 'status') and deal.status is not None:
                            if deal.status == DealStatus.COMPLETED:
                                successful_deals += 1
                            elif deal.status == DealStatus.PENDING:
                                pending_deals += 1
                            elif deal.status == DealStatus.FAILED:
                                failed_deals += 1
                    except Exception as e:
                        logger.warning(f"Error processing deal status for deal {getattr(deal, 'id', 'unknown')}: {str(e)}")
                        continue
                
                logger.debug(f"Deal status counts - Successful: {successful_deals}, Pending: {pending_deals}, Failed: {failed_deals}")
                
                # Safely calculate average completion time
                completion_times = []
                for deal in user_deals:
                    try:
                        if (hasattr(deal, 'status') and deal.status == DealStatus.COMPLETED and 
                            hasattr(deal, 'created_at') and deal.created_at is not None and 
                            hasattr(deal, 'updated_at') and deal.updated_at is not None):
                            
                            completion_time = (deal.updated_at - deal.created_at).total_seconds() / 3600  # in hours
                            completion_times.append(completion_time)
                    except Exception as e:
                        logger.warning(f"Error calculating completion time for deal {getattr(deal, 'id', 'unknown')}: {str(e)}")
                        continue
                        
                avg_completion_time = 0        
                if completion_times:
                    avg_completion_time = sum(completion_times) / len(completion_times)
                    logger.debug(f"Average completion time: {avg_completion_time} hours")
                
                # Safely find most active market
                market_activity = {}
                try:
                    for deal in user_deals:
                        if hasattr(deal, 'market_id') and deal.market_id is not None:
                            market_id = str(deal.market_id)
                            market_activity[market_id] = market_activity.get(market_id, 0) + 1
                    logger.debug(f"Market activity: {market_activity}")
                except Exception as e:
                    logger.warning(f"Error building market_activity: {str(e)}")
                    market_activity = {}
                
                # Safely get the most active market
                most_active_market = None
                try:
                    if market_activity:
                        most_active_market_id = max(market_activity.items(), key=lambda x: x[1])[0]
                        logger.debug(f"Most active market ID: {most_active_market_id}")
                        
                        # Safely get market details
                        if most_active_market_id and self.market_repository:
                            try:
                                market = await self.market_repository.get_by_id(UUID(most_active_market_id))
                                if market and hasattr(market, 'id') and hasattr(market, 'name') and market.name:
                                    most_active_market = {
                                        "id": str(market.id),
                                        "name": market.name,
                                        "deals_count": market_activity[most_active_market_id]
                                    }
                                    logger.debug(f"Most active market details: {most_active_market}")
                            except Exception as e:
                                logger.warning(f"Error getting market details for {most_active_market_id}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error determining most active market: {str(e)}")
                
                # Build the metrics response - ensure all values are JSON serializable
                result = {
                    "total_deals": total_deals,
                    "total_value": float(total_value) if isinstance(total_value, Decimal) else total_value,
                    "successful_deals": successful_deals,
                    "pending_deals": pending_deals,
                    "failed_deals": failed_deals,
                    "avg_completion_time": round(float(avg_completion_time), 2) if isinstance(avg_completion_time, Decimal) else round(avg_completion_time, 2),
                    "most_active_market": most_active_market
                }
                
                logger.info(f"Successfully calculated deal metrics for user {user_id}")
                return result
                
            except Exception as e:
                logger.error(f"Error calculating metrics: {str(e)}", exc_info=True)
                return default_response
                
        except Exception as e:
            logger.error(f"Error getting deal metrics: {str(e)}", exc_info=True)
            raise AnalyticsError(
                message=f"Failed to get deal metrics: {str(e)}",
                details={
                    "resource_type": "user_deals",
                    "resource_id": str(user_id),
                    "time_range": time_range
                }
            )

    async def get_performance_metrics(
        self,
        user_id: UUID,
        timeframe: str = "weekly"
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a user across different timeframes.
        
        Args:
            user_id: The ID of the user
            timeframe: Timeframe for metrics (daily, weekly, monthly)
            
        Returns:
            Dictionary containing performance metrics with time series data
        """
        try:
            # Validate timeframe
            if timeframe not in ["daily", "weekly", "monthly"]:
                raise ValidationError(f"Invalid timeframe: {timeframe}. Must be one of: daily, weekly, monthly")
            
            # Get metrics for requested timeframe
            metrics = await self.analytics_repository.get_performance_metrics(user_id, timeframe)
            
            # The frontend expects an object with daily, weekly, and monthly arrays
            # If not present in the result, add empty arrays for the other timeframes
            result = {
                "daily": [],
                "weekly": [],
                "monthly": []
            }
            
            # Add the requested timeframe data
            if timeframe in metrics:
                result[timeframe] = metrics[timeframe]
            
            # Get all timeframes data
            for tf in ["daily", "weekly", "monthly"]:
                if tf != timeframe:  # Skip the one we already fetched
                    try:
                        tf_metrics = await self.analytics_repository.get_performance_metrics(user_id, tf)
                        if tf in tf_metrics:
                            result[tf] = tf_metrics[tf]
                    except Exception as e:
                        logger.warning(f"Error fetching {tf} metrics: {str(e)}")
                        # Keep the default empty array
            
            return result
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            raise ServiceError(
                message=f"Failed to get performance metrics: {str(e)}",
                service="AnalyticsService",
                operation="get_performance_metrics"
            )

    # Helper method to ensure consistent timezone handling
    def _ensure_timezone_aware(self, dt: datetime) -> datetime:
        """
        Ensure datetime is timezone-aware by adding UTC timezone if it's naive.
        
        Args:
            dt: The datetime object to check
            
        Returns:
            A timezone-aware datetime object
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

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
            raise AnalyticsError(
                message=f"Failed to get market analytics: {str(e)}",
                details={
                    "resource_type": "market",
                    "resource_id": str(market_id)
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to get market comparison: {str(e)}",
                details={
                    "resource_type": "market_comparison",
                    "resource_id": ",".join([str(m_id) for m_id in market_ids])
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to get market price history: {str(e)}",
                details={
                    "resource_type": "market_price_history",
                    "resource_id": f"{market_id}:{product_id}"
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to get market availability: {str(e)}",
                details={
                    "resource_type": "market_availability",
                    "resource_id": str(market_id)
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to get market trends: {str(e)}",
                details={
                    "resource_type": "market_trends",
                    "resource_id": str(market_id),
                    "trend_period": trend_period
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to get market performance: {str(e)}",
                details={
                    "resource_type": "market_performance",
                    "resource_id": str(market_id)
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to update market analytics: {str(e)}",
                details={
                    "resource_type": "market_analytics",
                    "resource_id": str(market_id)
                }
            )

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
            raise AnalyticsError(
                message=f"Failed to aggregate market stats: {str(e)}",
                details={
                    "resource_type": "market_stats",
                    "resource_id": str(market_id)
                }
            )

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
                
            # Check cache first - Note: repository only needs deal_id, not user_id
            cached_analysis = await self.analytics_repository.get_deal_analysis(deal_id)
            if cached_analysis:
                logger.info(f"Found cached analysis for deal {deal_id}")
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
                
                # Cache the simplified analysis - Note: repository only needs deal_id
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
                days_until_expiry = (deal.expires_at - datetime.now(timezone.utc)).days
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
            
            # Fix the problematic comparison with expires_at
            # Original code:
            # "expiration_analysis": "Expires soon" if deal.expires_at and ((deal.expires_at.replace(tzinfo=None) if deal.expires_at.tzinfo else deal.expires_at) - datetime.utcnow()).days < 3 else "No immediate expiration"
            
            # Use this fixed version:
            now_utc = datetime.now(timezone.utc)
            expiration_analysis = "No immediate expiration"
            if deal.expires_at:
                expires_aware = self._ensure_timezone_aware(deal.expires_at)
                if (expires_aware - now_utc).days < 3:
                    expiration_analysis = "Expires soon"
            
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
                analysis_date=now_utc,
                expiration_analysis=expiration_analysis
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
            raise AnalyticsError(
                message=f"Failed to get deal analysis: {str(e)}",
                details={
                    "resource_type": "deal_analysis",
                    "resource_id": str(deal_id),
                    "user_id": str(user_id) if user_id else None
                }
            ) 

    async def get_goal_analytics(
        self,
        goal_id: UUID,
        user_id: UUID,
        start_date: Optional[datetime] = None
    ) -> GoalAnalytics:
        """
        Get analytics for a specific goal.
        
        Args:
            goal_id: ID of the goal
            user_id: ID of the user who owns the goal
            start_date: Optional start date for filtering analytics
            
        Returns:
            GoalAnalytics object with goal analytics data
            
        Raises:
            NotFoundException: If the goal is not found
            AnalyticsError: If analytics fetching fails
        """
        try:
            # Lazy import to avoid circular imports
            from core.services.goal import GoalService
            from core.database import get_session
            
            # If goal_service was not provided in constructor, create one temporarily
            if not self.goal_service:
                session = await get_session()
                self.goal_service = GoalService(session)
            
            # Get analytics from goal service
            analytics = await self.goal_service.get_goal_analytics(goal_id, user_id)
            
            # Ensure values are properly set to avoid frontend NaN issues
            if analytics.success_rate == 0 and analytics.total_matches > 0:
                # Calculate a meaningful success rate if not set but we have matches
                notification_threshold = 0.8  # Default threshold
                high_quality_matches = sum(1 for m in analytics.recent_matches if m.match_score >= notification_threshold)
                analytics.success_rate = high_quality_matches / analytics.total_matches if analytics.total_matches > 0 else 0.0
            
            # Ensure score values are never None to avoid NaN in frontend
            if analytics.best_match_score is None:
                analytics.best_match_score = 0.0
                
            if analytics.average_match_score is None:
                analytics.average_match_score = 0.0
                
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting goal analytics: {str(e)}")
            raise AnalyticsError(
                message=f"Failed to get goal analytics: {str(e)}",
                details={
                    "resource_type": "goal",
                    "resource_id": str(goal_id),
                    "user_id": str(user_id)
                }
            )
    
    async def get_goals_progress(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None
    ) -> List[GoalAnalytics]:
        """
        Get progress analytics for all goals of a user.
        
        Args:
            user_id: ID of the user
            start_date: Optional start date for filtering analytics
            
        Returns:
            List of GoalAnalytics objects for all user goals
            
        Raises:
            AnalyticsError: If analytics fetching fails
        """
        try:
            # Implementation would fetch all goals for the user
            # and get analytics for each one
            from core.services.goal import GoalService
            from core.database import get_session
            
            if not self.goal_service:
                session = await get_session()
                self.goal_service = GoalService(session)
                
            # This is a placeholder. The actual implementation should:
            # 1. Get all goals for the user
            # 2. Get analytics for each goal
            # 3. Return the list of analytics
            
            # For now, return an empty list to satisfy the API contract
            return []
            
        except Exception as e:
            logger.error(f"Error getting goals progress: {str(e)}")
            raise AnalyticsError(
                message=f"Failed to get goals progress: {str(e)}",
                details={
                    "resource_type": "goals_progress",
                    "user_id": str(user_id)
                }
            ) 