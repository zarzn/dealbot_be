"""Analytics repository module.

This module provides database operations for analytics data.
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
import random
from sqlalchemy import select, and_

from core.exceptions import DatabaseError, RepositoryError
from core.utils.redis import get_redis_client
from core.services.redis import get_redis_service
from core.database import get_session
from core.exceptions import ResourceNotFoundError
from core.utils.encoders import UUIDEncoder
from core.utils.logger import get_logger  # Import get_logger instead of logger
from core.models.user import User
from core.models.market import Market
from core.models.tracked_deal import TrackedDeal
from core.models.deal import Deal
from core.models.enums import DealStatus
from core.models.goal import Goal as GoalModel

logger = logging.getLogger(__name__)

class AnalyticsRepository:
    """Repository for analytics operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session."""
        self.session = session
        self._redis = None

    async def _get_redis(self):
        """Get Redis client lazily."""
        if self._redis is None:
            try:
                self._redis = await get_redis_service()
            except Exception as e:
                logger.warning(f"Failed to get Redis service for caching: {str(e)}")
                return None
        return self._redis

    async def get_deal_analysis(self, deal_id: UUID) -> Optional[Dict[str, Any]]:
        """Get deal analysis from cache.
        
        Args:
            deal_id: The UUID of the deal
            
        Returns:
            Dict containing analysis data or None if not found
        """
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
            raise DatabaseError(
                message=f"Failed to get market analytics: {str(e)}",
                operation="get_market_analytics"
            )

    async def get_market_comparison(
        self,
        market_ids: List[UUID],
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Compare metrics across multiple markets.
        
        Args:
            market_ids: List of market IDs to compare
            metrics: Optional list of specific metrics to compare
            
        Returns:
            Dict containing market comparison data
            
        Raises:
            DatabaseError: If there is an error retrieving comparison data
        """
        try:
            # For now, return mock data
            result = {}
            
            for market_id in market_ids:
                result[str(market_id)] = {
                    "performance": round(random.random() * 100, 2),
                    "reliability": round(random.random() * 100, 2),
                    "deals_count": random.randint(10, 1000),
                    "avg_discount": round(random.random() * 50, 2),
                    "avg_price": round(random.uniform(50, 500), 2)
                }
                
            return result
        except Exception as e:
            logger.error(f"Error comparing markets: {str(e)}")
            raise DatabaseError(
                message=f"Failed to compare markets: {str(e)}",
                operation="get_market_comparison"
            )

    async def get_price_history(
        self,
        market_id: UUID,
        product_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get price history for a product in a market.
        
        Args:
            market_id: Market ID
            product_id: Product ID
            start_date: Optional start date for history
            end_date: Optional end date for history
            
        Returns:
            Dict containing price history data
            
        Raises:
            DatabaseError: If there is an error retrieving price history
        """
        try:
            # For now, return mock data
            num_points = 30
            
            # If start and end dates provided, adjust number of points
            if start_date and end_date:
                days_diff = (end_date - start_date).days
                num_points = max(10, min(days_diff, 60))
            
            dates = []
            prices = []
            
            base_price = random.uniform(100, 1000)
            
            for i in range(num_points):
                price_date = datetime.now() - timedelta(days=num_points - i)
                
                if start_date and price_date < start_date:
                    continue
                    
                if end_date and price_date > end_date:
                    continue
                    
                price = base_price * (1 + random.uniform(-0.2, 0.2))
                base_price = price  # Price walks randomly
                
                dates.append(price_date.isoformat())
                prices.append(round(price, 2))
            
            return {
                "market_id": str(market_id),
                "product_id": product_id,
                "dates": dates,
                "prices": prices
            }
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get price history: {str(e)}",
                operation="get_price_history"
            )

    async def get_market_availability(self, market_id: UUID) -> Dict[str, Any]:
        """Get availability metrics for a market.
        
        Args:
            market_id: Market ID
            
        Returns:
            Dict containing availability metrics
            
        Raises:
            DatabaseError: If there is an error retrieving availability metrics
        """
        try:
            # For now, return mock data
            return {
                "market_id": str(market_id),
                "uptime_24h": round(random.uniform(95, 100), 2),
                "uptime_7d": round(random.uniform(90, 99.9), 2),
                "uptime_30d": round(random.uniform(90, 99.5), 2),
                "response_time_ms": random.randint(50, 500),
                "api_success_rate": round(random.uniform(95, 99.9), 2)
            }
        except Exception as e:
            logger.error(f"Error getting market availability: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get market availability: {str(e)}",
                operation="get_market_availability"
            )

    async def get_market_trends(
        self,
        market_id: UUID,
        trend_period: str = "24h"
    ) -> Dict[str, Any]:
        """Get trend analysis for a market.
        
        Args:
            market_id: Market ID
            trend_period: Period for trend analysis (24h, 7d, 30d)
            
        Returns:
            Dict containing trend analysis
            
        Raises:
            DatabaseError: If there is an error retrieving trend analysis
        """
        try:
            # Validate trend period
            valid_periods = ["24h", "7d", "30d"]
            if trend_period not in valid_periods:
                raise ValueError(f"Invalid trend period. Must be one of: {', '.join(valid_periods)}")
                
            # For now, return mock data
            num_points = 10
            if trend_period == "24h":
                num_points = 24
            elif trend_period == "7d":
                num_points = 7
            elif trend_period == "30d":
                num_points = 30
            
            # Generate mock trend data
            categories = ["Electronics", "Fashion", "Home", "Toys", "Sports"]
            trend_data = {}
            
            for category in categories:
                trend_data[category] = {
                    "volume": [random.randint(10, 100) for _ in range(num_points)],
                    "avg_price": [round(random.uniform(50, 500), 2) for _ in range(num_points)],
                    "discount_pct": [round(random.uniform(5, 30), 2) for _ in range(num_points)]
                }
            
            return {
                "market_id": str(market_id),
                "trend_period": trend_period,
                "categories": trend_data,
                "timestamps": [(datetime.now() - timedelta(hours=i)).isoformat() for i in range(num_points)]
            }
        except ValueError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            logger.error(f"Error getting market trends: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get market trends: {str(e)}",
                operation="get_market_trends"
            )

    async def get_market_performance(self, market_id: UUID) -> Dict[str, Any]:
        """Get market performance metrics.
        
        Args:
            market_id: Market ID
            
        Returns:
            Dict containing performance metrics
            
        Raises:
            DatabaseError: If there is an error retrieving performance metrics
        """
        try:
            # For now, return mock data
            return {
                "market_id": str(market_id),
                "deal_success_rate": round(random.uniform(60, 95), 2),
                "deals_total": random.randint(100, 10000),
                "deals_active": random.randint(50, 500),
                "avg_time_to_complete": random.randint(1, 10),
                "avg_discount": round(random.uniform(10, 40), 2),
                "customer_satisfaction": round(random.uniform(3, 5), 1),
                "price_accuracy": round(random.uniform(80, 99), 2)
            }
        except Exception as e:
            logger.error(f"Error getting market performance: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get market performance: {str(e)}",
                operation="get_market_performance"
            )

    async def update_market_analytics(
        self,
        market_id: UUID,
        analytics_data: Dict[str, Any]
    ) -> None:
        """Update market analytics data.
        
        Args:
            market_id: Market ID
            analytics_data: Analytics data to update
            
        Raises:
            DatabaseError: If there is an error updating analytics data
        """
        try:
            # In a real implementation, this would update the database
            logger.info(f"Would update market analytics for {market_id}: {analytics_data}")
        except Exception as e:
            logger.error(f"Error updating market analytics: {str(e)}")
            raise DatabaseError(
                message=f"Failed to update market analytics: {str(e)}",
                operation="update_market_analytics"
            )

    async def aggregate_market_stats(self, market_id: UUID) -> None:
        """Aggregate market statistics.
        
        Args:
            market_id: Market ID
            
        Raises:
            DatabaseError: If there is an error aggregating market stats
        """
        try:
            # In a real implementation, this would aggregate market statistics
            logger.info(f"Would aggregate market statistics for {market_id}")
        except Exception as e:
            logger.error(f"Error aggregating market stats: {str(e)}")
            raise DatabaseError(
                message=f"Failed to aggregate market stats: {str(e)}",
                operation="aggregate_market_stats"
            )

    async def get_dashboard_metrics(self, user_id: UUID) -> Dict[str, Any]:
        """Get real dashboard metrics for a user.
        
        Args:
            user_id: The UUID of the user
            
        Returns:
            Dict containing dashboard metrics
            
        Raises:
            DatabaseError: If there is an error retrieving metrics
        """
        try:
            from core.repositories.token import TokenRepository
            from core.repositories.deal import DealRepository
            from core.repositories.goal import GoalRepository
            from core.services.goal import GoalService
            
            # Initialize repositories
            token_repo = TokenRepository(self.session)
            deal_repo = DealRepository(self.session)
            goal_repo = GoalRepository(self.session)
            
            # Initialize GoalService for more accurate counting
            goal_service = GoalService(self.session)
            
            # Get real token balance
            token_balance = await token_repo.get_user_balance(str(user_id))
            balance_value = float(token_balance.balance) if token_balance else 0.0
            
            # Get token transactions for history
            token_transactions = await token_repo.get_user_transactions(
                str(user_id),
                limit=10,
                offset=0
            )
            
            # Process token history
            token_history = []
            for tx in token_transactions:
                token_history.append({
                    "date": tx.created_at.isoformat(),
                    "amount": float(tx.amount),
                    "type": "earned" if tx.amount > 0 else "spent",
                    "category": tx.type.lower()
                })
            
            # Calculate token spent/earned from transactions
            tokens_spent = sum(float(tx.amount) for tx in token_transactions if tx.amount < 0)
            tokens_earned = sum(float(tx.amount) for tx in token_transactions if tx.amount > 0)
            
            # Get deals statistics
            # Note: This assumes methods exist in DealRepository - modify as needed
            user_deals = await deal_repo.get_by_user(user_id)
            total_deals = len(user_deals) if user_deals else 0
            active_deals = sum(1 for deal in user_deals if hasattr(deal, 'status') and deal.status == DealStatus.ACTIVE.value)
            completed_deals = sum(1 for deal in user_deals if hasattr(deal, 'status') and deal.status == DealStatus.COMPLETED.value)
            saved_deals = sum(1 for deal in user_deals if hasattr(deal, 'is_saved') and deal.is_saved)
            
            # Calculate success rate and savings (if available)
            success_rate = (completed_deals / total_deals * 100) if total_deals > 0 else 0
            average_discount = 0.0
            total_savings = 0.0
            
            # Get goals statistics using GoalService for more accurate counts
            # Use count_goals with appropriate filters
            total_goals = await goal_service.count_goals(user_id)
            
            # For active goals, we want to ensure we don't count ones with passed deadlines
            # First get all goals with active status
            active_goals_query = select(GoalModel).where(
                and_(
                    GoalModel.user_id == user_id,
                    GoalModel.status == "active"
                )
            )
            active_goals_result = await self.session.execute(active_goals_query)
            active_goals_list = active_goals_result.scalars().all()
            
            # Now filter out those with passed deadlines
            # Use timezone-aware UTC datetime to avoid comparison issues
            now = datetime.now(timezone.utc)
            true_active_goals = []
            for goal in active_goals_list:
                # Skip goals without deadlines
                if not goal.deadline:
                    true_active_goals.append(goal)
                    continue
                    
                # Make goal deadline timezone-aware if it's naive
                goal_deadline = goal.deadline
                if goal_deadline.tzinfo is None:
                    goal_deadline = goal_deadline.replace(tzinfo=timezone.utc)
                    
                # Now compare safely
                if goal_deadline > now:
                    true_active_goals.append(goal)
            active_goals = len(true_active_goals)
            
            completed_goals = await goal_service.count_goals(user_id, {"status": "completed"})
            expired_goals = await goal_service.count_goals(user_id, {"status": "expired"})
            
            # Also count goals that are still marked as active but have passed deadlines
            expired_but_active = []
            for goal in active_goals_list:
                if not goal.deadline:
                    continue
                    
                # Make goal deadline timezone-aware if it's naive
                goal_deadline = goal.deadline
                if goal_deadline.tzinfo is None:
                    goal_deadline = goal_deadline.replace(tzinfo=timezone.utc)
                    
                # Now compare safely
                if goal_deadline <= now:
                    expired_but_active.append(goal)
            expired_goals += len(expired_but_active)
            
            # Log goals counts for debugging
            logger.debug(f"Goal counts for user {user_id}: total={total_goals}, active={active_goals}, completed={completed_goals}, expired={expired_goals}")
            
            # Calculate goal success rates
            average_success = (completed_goals / total_goals * 100) if total_goals > 0 else 0
            
            # Calculate match rate based on active goals with matches
            match_rate = 0.0
            if true_active_goals:
                goals_with_matches = sum(1 for g in true_active_goals if g.matches_found > 0)
                match_rate = (goals_with_matches / len(true_active_goals) * 100) if true_active_goals else 0
            
            # Get recent activity (combine from multiple sources)
            activity = []
            
            # Return compiled dashboard metrics
            return {
                "deals": {
                    "total": total_deals,
                    "active": active_deals,
                    "completed": completed_deals,
                    "saved": saved_deals,
                    "successRate": float(success_rate),
                    "averageDiscount": float(average_discount),
                    "totalSavings": float(total_savings)
                },
                "goals": {
                    "total": total_goals,
                    "active": active_goals,
                    "completed": completed_goals,
                    "expired": expired_goals,
                    "averageSuccess": float(average_success),
                    "matchRate": float(match_rate)
                },
                "tokens": {
                    "balance": balance_value,
                    "spent": {
                        "total": abs(tokens_spent),
                        "deals": 0.0,  # Would need more detailed categorization
                        "goals": 0.0,
                        "other": 0.0
                    },
                    "earned": {
                        "total": tokens_earned,
                        "referrals": 0.0,  # Would need more detailed categorization
                        "achievements": 0.0,
                        "other": 0.0
                    },
                    "history": token_history
                },
                "activity": activity  # Empty for now
            }
        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get dashboard metrics: {str(e)}",
                operation="get_dashboard_metrics"
            )

    async def get_performance_metrics(self, user_id: UUID, timeframe: str = "weekly") -> Dict[str, Any]:
        """Get performance metrics for a user across various timeframes.
        
        Args:
            user_id: The UUID of the user
            timeframe: Timeframe for metrics (daily, weekly, monthly)
            
        Returns:
            Dict containing performance metrics with time series data
            
        Raises:
            DatabaseError: If there is an error retrieving metrics
        """
        try:
            # Try to get from cache first
            redis = await self._get_redis()
            if redis:
                cache_key = f"performance_metrics:{user_id}:{timeframe}"
                cached_data = await redis.get(cache_key)
                if cached_data:
                    try:
                        return json.loads(cached_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in cached performance metrics for user {user_id}")
                        # Continue to fetch from database
            
            from sqlalchemy import func, select, cast, Date, extract
            from datetime import datetime, timedelta, timezone
            from core.models.deal import Deal
            from core.models.goal import Goal
            from core.models.token_transaction import TokenTransaction
            
            # Calculate date ranges based on timeframe
            # Ensure we're using timezone-aware datetime
            now = datetime.now(timezone.utc)
            
            # Define range and format based on timeframe
            if timeframe == "daily":
                # Last 14 days
                start_date = now - timedelta(days=14)
                date_extract = cast(TokenTransaction.created_at, Date)
                date_format = lambda d: d.strftime("%Y-%m-%d")
            elif timeframe == "weekly":
                # Last 12 weeks
                start_date = now - timedelta(weeks=12)
                # Extract week number - note this is a simplification
                date_extract = func.concat(
                    extract('year', TokenTransaction.created_at),
                    '-W',
                    extract('week', TokenTransaction.created_at)
                )
                date_format = lambda d: f"{d.year}-W{d.isocalendar()[1]}"
            elif timeframe == "monthly":
                # Last 12 months
                start_date = now - timedelta(days=365)
                date_extract = func.concat(
                    extract('year', TokenTransaction.created_at),
                    '-',
                    extract('month', TokenTransaction.created_at)
                )
                date_format = lambda d: d.strftime("%Y-%m")
            else:
                raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of: daily, weekly, monthly")
            
            # Query deals by date - use timezone-aware start_date
            deals_query = (
                select(
                    cast(Deal.created_at, Date).label('date'),
                    func.count(Deal.id).label('count')
                )
                .where(
                    Deal.user_id == user_id,
                    Deal.created_at >= start_date
                )
                .group_by('date')
                .order_by('date')
            )
            
            # Query goals by date - use timezone-aware start_date
            goals_query = (
                select(
                    cast(Goal.created_at, Date).label('date'),
                    func.count(Goal.id).label('count')
                )
                .where(
                    Goal.user_id == user_id,
                    Goal.created_at >= start_date
                )
                .group_by('date')
                .order_by('date')
            )
            
            # Query token transactions by date - use timezone-aware start_date
            tokens_query = (
                select(
                    cast(TokenTransaction.created_at, Date).label('date'),
                    func.sum(func.abs(TokenTransaction.amount)).label('count')
                )
                .where(
                    TokenTransaction.user_id == user_id,
                    TokenTransaction.created_at >= start_date
                )
                .group_by('date')
                .order_by('date')
            )
            
            # Execute queries with error handling
            try:
                deals_result = await self.session.execute(deals_query)
                deals_data = deals_result.fetchall()
            except Exception as e:
                logger.error(f"Error querying deals for metrics: {str(e)}")
                deals_data = []
                
            try:
                goals_result = await self.session.execute(goals_query)
                goals_data = goals_result.fetchall()
            except Exception as e:
                logger.error(f"Error querying goals for metrics: {str(e)}")
                goals_data = []
                
            try:
                tokens_result = await self.session.execute(tokens_query)
                tokens_data = tokens_result.fetchall()
            except Exception as e:
                logger.error(f"Error querying tokens for metrics: {str(e)}")
                tokens_data = []
            
            # Process data into required format with error handling
            deals_by_date = {}
            goals_by_date = {}
            tokens_by_date = {}
            
            for row in deals_data:
                try:
                    deals_by_date[date_format(row.date)] = row.count
                except Exception as e:
                    logger.error(f"Error processing deal row {row}: {str(e)}")
                    
            for row in goals_data:
                try:
                    goals_by_date[date_format(row.date)] = row.count
                except Exception as e:
                    logger.error(f"Error processing goal row {row}: {str(e)}")
                    
            for row in tokens_data:
                try:
                    tokens_by_date[date_format(row.date)] = float(row.count)
                except Exception as e:
                    logger.error(f"Error processing token row {row}: {str(e)}")
            
            # Generate date periods for consistent results
            date_periods = []
            
            if timeframe == "daily":
                # Generate daily periods for the last 14 days
                for i in range(14, -1, -1):
                    date = now - timedelta(days=i)
                    date_periods.append(date_format(date))
            elif timeframe == "weekly":
                # Generate weekly periods for the last 12 weeks
                for i in range(12, -1, -1):
                    date = now - timedelta(weeks=i)
                    date_periods.append(date_format(date))
            elif timeframe == "monthly":
                # Generate monthly periods for the last 12 months
                for i in range(12, -1, -1):
                    # Approximate month calculation
                    date = now - timedelta(days=i*30)
                    date_periods.append(date_format(date))
            
            # Compile data for response
            result = []
            
            for period in date_periods:
                if timeframe == "daily":
                    entry = {
                        "date": period,
                        "deals": deals_by_date.get(period, 0),
                        "goals": goals_by_date.get(period, 0),
                        "tokens": int(tokens_by_date.get(period, 0))
                    }
                elif timeframe == "weekly":
                    entry = {
                        "week": period,
                        "deals": deals_by_date.get(period, 0),
                        "goals": goals_by_date.get(period, 0),
                        "tokens": int(tokens_by_date.get(period, 0))
                    }
                elif timeframe == "monthly":
                    entry = {
                        "month": period,
                        "deals": deals_by_date.get(period, 0),
                        "goals": goals_by_date.get(period, 0),
                        "tokens": int(tokens_by_date.get(period, 0))
                    }
                
                result.append(entry)
            
            # Format response according to frontend expectations
            response = {
                timeframe: result
            }
            
            # Cache the result
            if redis:
                try:
                    await redis.set(
                        cache_key, 
                        json.dumps(response, cls=UUIDEncoder),
                        ex=300  # Cache for 5 minutes
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache performance metrics: {str(e)}")
            
            return response
            
        except ValueError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            raise DatabaseError(
                message=f"Failed to get performance metrics: {str(e)}",
                operation="get_performance_metrics"
            ) 