"""Recommendation service module."""

from typing import List, Optional, Any
from uuid import UUID
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.models.deal import DealRecommendation
from core.repositories.deal import DealRepository
from core.repositories.goal import GoalRepository
from core.exceptions import RecommendationError

logger = logging.getLogger(__name__)

class RecommendationService:
    """Service for generating deal recommendations."""

    def __init__(
        self,
        db: AsyncSession,
        deal_repository: DealRepository,
        goal_repository: GoalRepository
    ):
        self.db = db
        self.deal_repository = deal_repository
        self.goal_repository = goal_repository

    async def get_recommendations(
        self,
        user_id: UUID,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[DealRecommendation]:
        """Get personalized deal recommendations.
        
        Args:
            user_id: User ID
            category: Optional category filter
            limit: Maximum number of recommendations
            
        Returns:
            List[DealRecommendation]: List of recommended deals
            
        Raises:
            RecommendationError: If recommendation generation fails
        """
        try:
            # Get user's goals
            goals = await self.goal_repository.get_active_goals(user_id)
            
            # Get matching deals
            deals = await self.deal_repository.get_deals_for_goals(goals, limit)
            
            # Convert to recommendations
            recommendations = []
            for deal in deals:
                recommendations.append(
                    DealRecommendation(
                        id=deal.id,
                        title=deal.title,
                        description=deal.description,
                        price=deal.price,
                        original_price=deal.original_price,
                        source=deal.source,
                        url=deal.url,
                        image_url=deal.image_url,
                        score=deal.score,
                        matching_goals=[goal.id for goal in goals if self._matches_goal(deal, goal)],
                        created_at=datetime.utcnow()
                    )
                )
            
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            raise RecommendationError(f"Failed to generate recommendations: {str(e)}")
            
    def _matches_goal(self, deal: Any, goal: Any) -> bool:
        """Check if a deal matches a goal's criteria."""
        try:
            # Check price constraints
            if goal.constraints.get('max_price') and deal.price > goal.constraints['max_price']:
                return False
            if goal.constraints.get('min_price') and deal.price < goal.constraints['min_price']:
                return False
                
            # Check category
            if goal.constraints.get('category') and goal.constraints['category'] != deal.category:
                return False
                
            # Check keywords
            if goal.constraints.get('keywords'):
                keywords = [kw.lower() for kw in goal.constraints['keywords']]
                deal_text = f"{deal.title} {deal.description}".lower()
                if not any(kw in deal_text for kw in keywords):
                    return False
                    
            return True
            
        except Exception as e:
            logger.warning(f"Error matching deal to goal: {str(e)}")
            return False 