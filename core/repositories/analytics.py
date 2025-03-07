"""Analytics repository module.

This module provides database operations for analytics data.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError, RepositoryError
from core.utils.redis import get_redis_client
from core.services.redis import get_redis_service, UUIDEncoder
from core.database import get_session
from core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

class AnalyticsRepository:
    """Repository for analytics operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._redis = None

    async def _get_redis(self):
        """Get Redis client lazily."""
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis

    async def get_deal_analysis(self, deal_id: UUID) -> Optional[Dict[str, Any]]:
        """Get deal analysis from cache.
        
        Args:
            deal_id: The UUID of the deal
            
        Returns:
            Dict containing analysis data or None if not found
        """
        # TEMPORARY: Disable Redis caching to avoid recursion issues
        logger.info(f"Deal analysis cache temporarily disabled for deal_id {deal_id}")
        return None
        
        # Commented out code below
        try:
            redis = await self._get_redis()
            if not redis:
                return None
            
            # Convert UUID to string for cache key    
            deal_id_str = str(deal_id)
            
            # Try to get from cache
            cache_key = f"deal:analysis:{deal_id_str}"
            cached_data = await redis.get(cache_key)
            
            if not cached_data:
                return None
                
            return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error getting deal analysis from cache: {str(e)}")
            # Return None instead of raising to allow fallback to calculation
            return None

    async def save_deal_analysis(
        self,
        deal_id: UUID,
        analysis_data: Dict[str, Any],
        ttl: int = 3600  # Default 1 hour cache
    ) -> None:
        """Save deal analysis to cache.
        
        Args:
            deal_id: The UUID of the deal
            analysis_data: Dict containing analysis data
            ttl: Time to live in seconds
        """
        # TEMPORARY: Disable Redis caching to avoid recursion issues
        logger.info(f"Deal analysis cache temporarily disabled for deal_id {deal_id}")
        return
        
        # Commented out code below
        try:
            redis = await self._get_redis()
            if not redis:
                return
                
            # Convert UUID to string for cache key
            deal_id_str = str(deal_id)
            
            # Save to cache
            cache_key = f"deal:analysis:{deal_id_str}"
            
            # First convert any UUID objects to strings
            # Use a simpler approach to avoid recursion issues
            serializable_data = {}
            for key, value in analysis_data.items():
                if isinstance(value, UUID):
                    serializable_data[key] = str(value)
                else:
                    serializable_data[key] = value
            
            await redis.set(
                cache_key,
                json.dumps(serializable_data, cls=UUIDEncoder),
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Error saving deal analysis to cache: {str(e)}")
            # Continue execution without raising

    async def get_market_analytics(self, market_id: UUID) -> Dict[str, Any]:
        """Get analytics for a specific market.
        
        Args:
            market_id: The UUID of the market to get analytics for
            
        Returns:
            Dict containing market analytics data
            
        Raises:
            DatabaseError: If there is an error retrieving the analytics
        """
        try:
            # In a real implementation, this would query analytics tables
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
            logger.error(f"Error getting market analytics: {str(e)}")
            raise DatabaseError(f"Failed to get market analytics: {str(e)}")

    async def get_market_comparison(
        self,
        market_ids: List[UUID],
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Compare multiple markets.
        
        Args:
            market_ids: List of market UUIDs to compare
            metrics: Optional list of specific metrics to compare
            
        Returns:
            Dict containing market comparison data
            
        Raises:
            DatabaseError: If there is an error comparing markets
        """
        try:
            # In a real implementation, this would query analytics tables
            # For now, returning mock data
            return {
                "comparison_date": datetime.now().isoformat(),
                "markets": [
                    {
                        "id": str(market_id),
                        "metrics": {
                            "total_products": 1000000,
                            "active_deals": 5000,
                            "average_discount": 25.5,
                            "response_time": "120ms",
                            "success_rate": 99.5
                        }
                    }
                    for market_id in market_ids
                ],
                "summary": {
                    "best_prices": "Amazon",
                    "most_deals": "Walmart",
                    "fastest_updates": "Amazon"
                }
            }
        except Exception as e:
            logger.error(f"Error comparing markets: {str(e)}")
            raise DatabaseError(f"Failed to compare markets: {str(e)}")

    async def get_price_history(
        self,
        market_id: UUID,
        product_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get price history for a product in a market.
        
        Args:
            market_id: The UUID of the market
            product_id: The product identifier
            start_date: Optional start date for history range
            end_date: Optional end date for history range
            
        Returns:
            Dict containing price history data
            
        Raises:
            DatabaseError: If there is an error retrieving price history
        """
        try:
            # In a real implementation, this would query price history tables
            # For now, returning mock data
            return {
                "market_id": str(market_id),
                "product_id": product_id,
                "price_points": [
                    {"date": "2024-02-01", "price": 99.99},
                    {"date": "2024-02-02", "price": 89.99},
                    {"date": "2024-02-03", "price": 79.99}
                ],
                "average_price": 89.99,
                "lowest_price": 79.99,
                "highest_price": 99.99,
                "price_trend": "decreasing"
            }
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise DatabaseError(f"Failed to get price history: {str(e)}")

    async def get_market_availability(self, market_id: UUID) -> Dict[str, Any]:
        """Get availability metrics for a market.
        
        Args:
            market_id: The UUID of the market
            
        Returns:
            Dict containing availability metrics
            
        Raises:
            DatabaseError: If there is an error retrieving availability data
        """
        try:
            # In a real implementation, this would query availability tables
            # For now, returning mock data
            return {
                "market_id": str(market_id),
                "total_products": 1000000,
                "available_products": 950000,
                "out_of_stock": 50000,
                "availability_rate": 95.0,
                "last_checked": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting market availability: {str(e)}")
            raise DatabaseError(f"Failed to get market availability: {str(e)}")

    async def get_market_trends(
        self,
        market_id: UUID,
        trend_period: str = "24h"
    ) -> Dict[str, Any]:
        """Get market trends.
        
        Args:
            market_id: The UUID of the market
            trend_period: Time period for trends (e.g. "24h", "7d")
            
        Returns:
            Dict containing market trend data
            
        Raises:
            DatabaseError: If there is an error retrieving trends
        """
        try:
            # In a real implementation, this would query trends tables
            # For now, returning mock data
            return {
                "trend_period": trend_period,
                "top_trending": [
                    {"category": "Electronics", "change": 15},
                    {"category": "Home & Kitchen", "change": 10},
                    {"category": "Fashion", "change": 5}
                ],
                "price_trends": {
                    "Electronics": -5.2,
                    "Home & Kitchen": -3.1,
                    "Fashion": -2.5
                },
                "category_trends": [
                    {"name": "Electronics", "trend": "up"},
                    {"name": "Home & Kitchen", "trend": "stable"},
                    {"name": "Fashion", "trend": "down"}
                ],
                "search_trends": [
                    {"term": "laptop", "count": 1500},
                    {"term": "coffee maker", "count": 1200},
                    {"term": "sneakers", "count": 1000}
                ]
            }
        except Exception as e:
            logger.error(f"Error getting market trends: {str(e)}")
            raise DatabaseError(f"Failed to get market trends: {str(e)}")

    async def get_market_performance(self, market_id: UUID) -> Dict[str, Any]:
        """Get market performance metrics.
        
        Args:
            market_id: The UUID of the market
            
        Returns:
            Dict containing performance metrics
            
        Raises:
            DatabaseError: If there is an error retrieving performance data
        """
        try:
            # In a real implementation, this would query performance tables
            # For now, returning mock data
            return {
                "market_id": str(market_id),
                "uptime": 99.9,
                "response_times": {
                    "p50": 120,
                    "p90": 200,
                    "p99": 500
                },
                "error_rates": {
                    "total": 0.1,
                    "timeout": 0.05,
                    "connection": 0.03,
                    "other": 0.02
                },
                "success_rates": {
                    "total": 99.9,
                    "search": 99.95,
                    "details": 99.85,
                    "pricing": 99.9
                },
                "api_usage": {
                    "total": 1000000,
                    "search": 500000,
                    "details": 300000,
                    "pricing": 200000
                }
            }
        except Exception as e:
            logger.error(f"Error getting market performance: {str(e)}")
            raise DatabaseError(f"Failed to get market performance: {str(e)}")

    async def update_market_analytics(
        self,
        market_id: UUID,
        analytics_data: Dict[str, Any]
    ) -> None:
        """Update analytics data for a market.
        
        Args:
            market_id: The UUID of the market
            analytics_data: Dict containing analytics data to update
            
        Raises:
            DatabaseError: If there is an error updating analytics data
        """
        try:
            # In a real implementation, this would update analytics tables
            # For now, just logging the update
            logger.info(f"Updating analytics for market {market_id}: {analytics_data}")
        except Exception as e:
            logger.error(f"Error updating market analytics: {str(e)}")
            raise DatabaseError(f"Failed to update market analytics: {str(e)}")

    async def aggregate_market_stats(self, market_id: UUID) -> None:
        """Aggregate market statistics.
        
        Args:
            market_id: The UUID of the market
            
        Raises:
            DatabaseError: If there is an error aggregating statistics
        """
        try:
            # In a real implementation, this would aggregate statistics
            # For now, just logging the aggregation
            logger.info(f"Aggregating stats for market {market_id}")
        except Exception as e:
            logger.error(f"Error aggregating market stats: {str(e)}")
            raise DatabaseError(f"Failed to aggregate market stats: {str(e)}") 