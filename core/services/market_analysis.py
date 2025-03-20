"""Market analysis and opportunity detection service."""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.user import User
from core.models.market import Market
from core.models.deal import Deal
from core.models.price_history import PricePoint
from core.exceptions.base_exceptions import NotFoundError, ValidationError
from core.utils.logger import get_logger

logger = get_logger(__name__)


class MarketAnalysisService:
    """Service for analyzing markets and detecting opportunities."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the market analysis service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def detect_market_opportunities(
        self,
        min_price_drop_percent: float = 5.0,
        min_volume_increase_percent: float = 20.0,
        lookback_days: int = 7,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Detect market opportunities based on price drops and volume increases.
        
        Args:
            min_price_drop_percent: Minimum price drop percentage to consider
            min_volume_increase_percent: Minimum volume increase percentage to consider
            lookback_days: Number of days to look back for analysis
            user_id: Optional user ID to personalize opportunities
            
        Returns:
            List of market opportunities
        """
        # Get markets with good opportunities
        markets_with_data = await self._get_markets_with_opportunity_signals(
            min_price_drop_percent=min_price_drop_percent,
            min_volume_increase_percent=min_volume_increase_percent,
            lookback_days=lookback_days
        )
        
        # Format opportunities for return
        opportunities = []
        for market_data in markets_with_data:
            market = market_data["market"]
            price_change = market_data["price_change"]
            volume_change = market_data.get("volume_change", 0)
            
            # Create opportunity data
            opportunity = {
                "market_id": str(market.id),
                "market_name": market.name,
                "market_description": market.description,
                "market_category": market.category,
                "price_change_percent": round(price_change, 2),
                "volume_change_percent": round(volume_change, 2) if volume_change else None,
                "current_price": market_data.get("current_price"),
                "previous_price": market_data.get("previous_price"),
                "opportunity_score": self._calculate_opportunity_score(price_change, volume_change),
                "detected_at": datetime.utcnow(),
                "opportunity_type": "price_drop" if abs(price_change) > abs(volume_change) else "volume_increase"
            }
            
            opportunities.append(opportunity)
        
        # Sort by opportunity score descending
        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        
        return opportunities
    
    async def notify_users_of_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
        max_notifications_per_user: int = 3,
        user_preferences: Optional[Dict[UUID, Dict[str, Any]]] = None
    ) -> int:
        """Notify users about market opportunities.
        
        Args:
            opportunities: List of market opportunities
            max_notifications_per_user: Maximum number of notifications to send per user
            user_preferences: Optional dictionary of user preferences for personalization
            
        Returns:
            Number of notifications sent
        """
        if not opportunities:
            return 0
            
        # Import here to avoid circular imports
        from core.notifications import TemplatedNotificationService
        
        notification_service = TemplatedNotificationService(self.db)
        
        # Get active users
        result = await self.db.execute(
            select(User).filter(User.status == "active")
        )
        users = result.scalars().all()
        
        # Track notification count
        notification_count = 0
        
        # For each user, find and send their top opportunities
        for user in users:
            # Get user's preferences if available
            preferences = user_preferences.get(user.id, {}) if user_preferences else {}
            
            # Personalize opportunities for this user
            user_opportunities = await self._personalize_opportunities(
                opportunities, 
                user.id,
                preferences
            )
            
            # Limit to top opportunities
            user_opportunities = user_opportunities[:max_notifications_per_user]
            
            # Send notifications for each opportunity
            for opportunity in user_opportunities:
                try:
                    await notification_service.send_notification(
                        template_id="market_opportunity",
                        user_id=user.id,
                        template_params={
                            "market_name": opportunity["market_name"],
                            "price_change": abs(opportunity["price_change_percent"]),
                            "opportunity_type": opportunity["opportunity_type"],
                            "market_category": opportunity["market_category"]
                        },
                        metadata={
                            "market_id": opportunity["market_id"],
                            "opportunity_score": opportunity["opportunity_score"],
                            "opportunity_type": opportunity["opportunity_type"],
                            "price_change_percent": opportunity["price_change_percent"],
                            "volume_change_percent": opportunity.get("volume_change_percent")
                        },
                        action_url=f"/markets/{opportunity['market_id']}"
                    )
                    notification_count += 1
                except Exception as e:
                    logger.error(f"Failed to send opportunity notification to user {user.id}: {str(e)}")
        
        return notification_count
    
    async def _get_markets_with_opportunity_signals(
        self,
        min_price_drop_percent: float,
        min_volume_increase_percent: float,
        lookback_days: int
    ) -> List[Dict[str, Any]]:
        """Get markets showing opportunity signals.
        
        Args:
            min_price_drop_percent: Minimum price drop percentage to consider
            min_volume_increase_percent: Minimum volume increase percentage to consider
            lookback_days: Number of days to look back for analysis
            
        Returns:
            List of markets with opportunity signals
        """
        # Get all active markets
        result = await self.db.execute(
            select(Market).filter(Market.status == "active")
        )
        markets = result.scalars().all()
        
        opportunities = []
        current_time = datetime.utcnow()
        start_time = current_time - timedelta(days=lookback_days)
        
        # For each market, check if it shows opportunity signals
        for market in markets:
            try:
                # Get price history for this market
                result = await self.db.execute(
                    select(PricePoint)
                    .filter(
                        PricePoint.market_id == market.id,
                        PricePoint.timestamp >= start_time
                    )
                    .order_by(PricePoint.timestamp)
                )
                price_points = result.scalars().all()
                
                if len(price_points) < 2:
                    continue  # Not enough data
                
                # Compare prices
                current_price = price_points[-1].price
                previous_price = price_points[0].price
                
                if previous_price == 0:
                    continue  # Avoid division by zero
                
                price_change_percent = ((current_price - previous_price) / previous_price) * 100
                
                # If price increased, skip
                if price_change_percent >= 0:
                    continue
                
                # Check if price drop meets threshold
                if abs(price_change_percent) < min_price_drop_percent:
                    continue
                
                # Get trading volume if available
                volume_change_percent = None
                if hasattr(price_points[0], 'volume') and hasattr(price_points[-1], 'volume'):
                    if price_points[0].volume > 0:
                        volume_change_percent = ((price_points[-1].volume - price_points[0].volume) / price_points[0].volume) * 100
                
                # Add to opportunities if either criteria is met
                if abs(price_change_percent) >= min_price_drop_percent or (volume_change_percent and volume_change_percent >= min_volume_increase_percent):
                    opportunities.append({
                        "market": market,
                        "price_change": price_change_percent,
                        "volume_change": volume_change_percent,
                        "current_price": current_price,
                        "previous_price": previous_price
                    })
                    
            except Exception as e:
                logger.warning(f"Error analyzing market {market.id}: {str(e)}")
        
        return opportunities
    
    async def _personalize_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
        user_id: UUID,
        preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Personalize opportunities for a specific user.
        
        Args:
            opportunities: List of market opportunities
            user_id: User ID to personalize for
            preferences: User preferences
            
        Returns:
            Personalized and sorted opportunities
        """
        if not opportunities:
            return []
            
        # Create a copy to avoid modifying original
        personalized = opportunities.copy()
        
        # Get user's market interaction history
        result = await self.db.execute(
            select(Deal.market_id)
            .filter(Deal.user_id == user_id)
            .group_by(Deal.market_id)
        )
        user_markets = [str(m[0]) for m in result.all()]
        
        # Get user's preferred categories (from preferences or history)
        preferred_categories = preferences.get("preferred_categories", [])
        
        if not preferred_categories:
            # Try to infer from history
            result = await self.db.execute(
                select(Market.category)
                .join(Deal, Market.id == Deal.market_id)
                .filter(Deal.user_id == user_id)
                .group_by(Market.category)
                .order_by(desc(func.count()))
                .limit(3)
            )
            preferred_categories = [c[0] for c in result.all()]
        
        # Score each opportunity based on user's history and preferences
        for opportunity in personalized:
            base_score = opportunity["opportunity_score"]
            personalization_score = 0
            
            # Boost score if user has interacted with this market before
            if opportunity["market_id"] in user_markets:
                personalization_score += 2
                
            # Boost score if market is in user's preferred categories
            if opportunity["market_category"] in preferred_categories:
                personalization_score += 1
            
            # Update the opportunity score
            opportunity["opportunity_score"] = base_score + personalization_score
        
        # Sort by personalized score
        personalized.sort(key=lambda x: x["opportunity_score"], reverse=True)
        
        return personalized
    
    def _calculate_opportunity_score(
        self,
        price_change_percent: float,
        volume_change_percent: Optional[float]
    ) -> float:
        """Calculate an opportunity score based on price and volume changes.
        
        Args:
            price_change_percent: Price change percentage
            volume_change_percent: Volume change percentage or None
            
        Returns:
            Opportunity score (higher is better)
        """
        # For price drops, the percentage is negative, so we use abs()
        price_score = abs(price_change_percent) / 5.0  # 5% drop = 1 point
        
        # Volume score only applies if we have volume data
        volume_score = 0
        if volume_change_percent is not None:
            volume_score = max(0, volume_change_percent / 20.0)  # 20% increase = 1 point
        
        # Combine scores, with price having more weight
        return (price_score * 0.7) + (volume_score * 0.3) 