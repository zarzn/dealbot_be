from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from redis.asyncio import Redis
import logging

# Import models
from core.models.deal import (
    Deal,
    DealStatus,
    DealUpdate,
    PriceHistory,
    DealSearchFilters
)
from core.models.goal import Goal, GoalStatus
from core.models.deal_score import DealScore
from core.models.base import Base
from core.models.user import User

# Import exceptions
from core.exceptions import (
    DatabaseError,
    DealNotFoundError,
    InvalidDealDataError
)

from core.utils.redis import get_redis_client
from core.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

class DealRepository(BaseRepository[Deal]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Deal)
        self.redis: Redis = get_redis_client()

    async def create(self, deal_data: Dict[str, Any]) -> Deal:
        """Create a new deal"""
        try:
            deal = Deal(**deal_data)
            self.db.add(deal)
            await self.db.commit()
            await self.db.refresh(deal)
            return deal
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal data: {str(e)}")

    async def get_by_id(self, deal_id: UUID) -> Optional[Deal]:
        """Get deal by ID"""
        try:
            result = await self.db.execute(
                select(Deal).where(Deal.id == deal_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_by_id")

    async def update(self, deal_id: UUID, deal_data: DealUpdate) -> Deal:
        """Update deal"""
        try:
            deal = await self.get_by_id(deal_id)
            if not deal:
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            for field, value in deal_data.dict(exclude_unset=True).items():
                setattr(deal, field, value)
                
            deal.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(deal)
            return deal
        except DealNotFoundError:
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "update_deal")

    async def delete(self, deal_id: UUID) -> None:
        """Delete deal"""
        try:
            deal = await self.get_by_id(deal_id)
            if not deal:
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            await self.db.delete(deal)
            await self.db.commit()
        except DealNotFoundError:
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to delete deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "delete_deal")

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[DealSearchFilters] = None,
        sort_by: Optional[str] = None
    ) -> List[Deal]:
        """
        Search for deals with advanced filtering and sorting.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            filters: Optional search filters
            sort_by: Optional sort parameter
            
        Returns:
            List of matching deals
        """
        try:
            # Build base query
            base_query = self.build_search_query(query)
            
            # Apply filters if provided
            if filters:
                base_query = self.apply_filters(base_query, filters)
                
            # Apply sorting
            if sort_by:
                base_query = self.apply_sorting(base_query, sort_by)
                
            # Execute query with limit
            result = await self.db.execute(base_query.limit(limit))
            deals = result.scalars().all()
            
            # Enrich deals with additional data
            enriched_deals = []
            for deal in deals:
                deal_dict = deal.__dict__
                deal_dict["price_history"] = await self.get_price_history(deal.id)
                deal_dict["market_analysis"] = await self.get_market_analysis(deal)
                enriched_deals.append(deal_dict)
                
            return enriched_deals
            
        except SQLAlchemyError as e:
            logger.error(f"Search query failed: {str(e)}")
            raise DatabaseError(f"Failed to execute search: {str(e)}", "search")
            
    def build_search_query(self, query: str):
        """Build base search query."""
        return select(Deal).where(
            or_(
                Deal.title.ilike(f"%{query}%"),
                Deal.description.ilike(f"%{query}%"),
                Deal.category.ilike(f"%{query}%")
            )
        ).where(Deal.status == DealStatus.ACTIVE)
        
    def apply_filters(self, query: Any, filters: DealSearchFilters):
        """Apply filters to query."""
        if filters.min_price:
            query = query.where(Deal.price >= filters.min_price)
        if filters.max_price:
            query = query.where(Deal.price <= filters.max_price)
        if filters.categories:
            query = query.where(Deal.category.in_(filters.categories))
        return query
        
    def apply_sorting(self, query: Any, sort_by: str):
        """Apply sorting to query."""
        sort_map = {
            "price_asc": Deal.price.asc(),
            "price_desc": Deal.price.desc(),
            "expiry": Deal.expires_at.asc(),
            "relevance": Deal.created_at.desc()
        }
        return query.order_by(sort_map.get(sort_by, Deal.created_at.desc()))
        
    async def get_market_analysis(self, deal: Deal) -> Dict[str, Any]:
        """Get market analysis for a deal."""
        try:
            # Get average market price
            avg_price_query = select(func.avg(Deal.price)).where(
                and_(
                    Deal.category == deal.category,
                    Deal.status == DealStatus.ACTIVE,
                    Deal.id != deal.id
                )
            )
            result = await self.db.execute(avg_price_query)
            avg_market_price = result.scalar_one_or_none() or deal.price
            
            # Get price trend
            price_history = await self.get_price_history(deal.id)
            price_trend = self.calculate_price_trend(price_history)
            
            # Get deal score
            deal_score = await self.calculate_deal_score(deal, avg_market_price)
            
            return {
                "average_market_price": float(avg_market_price),
                "price_trend": price_trend,
                "deal_score": deal_score
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market analysis: {str(e)}")
            return {
                "average_market_price": float(deal.price),
                "price_trend": "stable",
                "deal_score": 0.0
            }
            
    def calculate_price_trend(self, price_history: List[Dict]) -> str:
        """Calculate price trend from history."""
        if not price_history or len(price_history) < 2:
            return "stable"
            
        prices = [float(p["price"]) for p in price_history]
        first_price = prices[0]
        last_price = prices[-1]
        
        change_percent = ((last_price - first_price) / first_price) * 100
        
        if change_percent <= -10:
            return "falling"
        elif change_percent >= 10:
            return "rising"
        else:
            return "stable"
            
    async def calculate_deal_score(self, deal: Deal, avg_market_price: float) -> float:
        """Calculate deal score based on various factors."""
        try:
            # Base score from price comparison
            price_ratio = float(deal.price) / avg_market_price
            base_score = max(0, min(100, (1 - price_ratio) * 100))
            
            # Adjust for source reliability
            source_reliability = self.get_source_reliability(deal.source)
            
            # Adjust for price history
            price_history = await self.get_price_history(deal.id)
            price_stability = self.calculate_price_stability(price_history)
            
            # Calculate final score
            final_score = (
                base_score * 0.6 +  # Price comparison weight
                source_reliability * 20 +  # Source reliability weight
                price_stability * 20  # Price stability weight
            )
            
            return round(max(0, min(100, final_score)), 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate deal score: {str(e)}")
            return 0.0
            
    def get_source_reliability(self, source: str) -> float:
        """Get reliability score for a source."""
        reliability_scores = {
            "amazon": 0.95,
            "walmart": 0.90,
            "bestbuy": 0.85,
            "target": 0.85,
            "ebay": 0.75,
            "other": 0.60
        }
        return reliability_scores.get(source.lower(), 0.60)
        
    def calculate_price_stability(self, price_history: List[Dict]) -> float:
        """Calculate price stability score."""
        if not price_history or len(price_history) < 2:
            return 0.5
            
        prices = [float(p["price"]) for p in price_history]
        avg_price = sum(prices) / len(prices)
        
        # Calculate coefficient of variation
        std_dev = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5
        cv = std_dev / avg_price
        
        # Convert to stability score (0-1)
        stability = max(0, min(1, 1 - cv))
        
        return stability

    async def get_price_history(
        self,
        product_name: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a product"""
        try:
            stmt = text("""
                SELECT date_trunc('day', created_at) as date,
                       avg(price) as avg_price,
                       min(price) as min_price,
                       max(price) as max_price,
                       count(*) as data_points
                FROM deals
                WHERE title ILIKE :product_name
                AND created_at >= :start_date
                GROUP BY date_trunc('day', created_at)
                ORDER BY date_trunc('day', created_at) DESC
            """)
            
            start_date = datetime.utcnow() - timedelta(days=days)
            result = await self.db.execute(
                stmt,
                {"product_name": f"%{product_name}%", "start_date": start_date}
            )
            
            return [
                {
                    "date": row.date.isoformat(),
                    "avg_price": float(row.avg_price),
                    "min_price": float(row.min_price),
                    "max_price": float(row.max_price),
                    "data_points": row.data_points
                }
                for row in result
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get price history: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_price_history")

    async def get_deal_scores(
        self,
        product_name: str,
        limit: int = 10
    ) -> List[float]:
        """Get historical deal scores for a product"""
        try:
            # First find deals matching the product name
            deals_stmt = select(Deal.id).where(
                Deal.title.ilike(f"%{product_name}%")
            ).limit(20)  # Get more deals than needed to ensure we have enough scores
            
            deals_result = await self.db.execute(deals_stmt)
            deal_ids = [row.id for row in deals_result.scalars().all()]
            
            if not deal_ids:
                return []
            
            # Then get scores for those deals
            scores_stmt = select(DealScore.score).where(
                DealScore.deal_id.in_(deal_ids)
            ).order_by(DealScore.created_at.desc()).limit(limit)
            
            scores_result = await self.db.execute(scores_stmt)
            return [float(row.score) for row in scores_result.scalars().all()]
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal scores: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_deal_scores")

    async def create_deal_score(
        self,
        deal_id: UUID,
        score: float,
        confidence: float = 1.0,
        score_type: str = "ai",
        score_metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store deal score in the database"""
        try:
            # Create new DealScore object
            deal_score = DealScore(
                deal_id=deal_id,
                score=score,
                confidence=confidence,
                score_type=score_type,
                score_metadata=score_metadata or {}
                # 'timestamp' is automatically set by the model's default value
            )
            
            # Add to database
            self.db.add(deal_score)
            await self.db.flush()
            
            logger.info(
                f"Created deal score {deal_score.id} for deal {deal_id} with score {score}"
            )
            
            return deal_score.id
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal score: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal score data: {str(e)}")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating deal score: {str(e)}")
            raise DatabaseError(f"Database error creating deal score: {str(e)}", "create_deal_score")

    async def get_active_goals(self) -> List[Dict[str, Any]]:
        """Get active goals for deal monitoring"""
        try:
            stmt = text("""
                SELECT g.id,
                       g.item_category,
                       g.constraints,
                       g.deadline,
                       g.priority
                FROM goals g
                WHERE g.status = 'active'
                AND (g.deadline IS NULL OR g.deadline > :now)
                ORDER BY g.priority DESC
            """)
            
            result = await self.db.execute(
                stmt,
                {"now": datetime.utcnow()}
            )
            
            return [
                {
                    "id": str(row.id),
                    "item_category": row.item_category,
                    "constraints": row.constraints,
                    "deadline": row.deadline.isoformat() if row.deadline else None,
                    "priority": row.priority
                }
                for row in result
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active goals: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_active_goals")

    async def get_active_deals(self, page: int = 1, per_page: int = 20) -> List[Deal]:
        """Get paginated list of active deals"""
        try:
            result = await self.db.execute(
                select(Deal)
                .where(Deal.status == DealStatus.ACTIVE)
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active deals: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_active_deals")

    async def get_deals_by_source(self, source: str, limit: int = 100) -> List[Deal]:
        """Get deals by source with limit"""
        try:
            result = await self.db.execute(
                select(Deal)
                .where(Deal.source == source)
                .limit(limit)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deals by source: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_deals_by_source")

    async def get_deal_metrics(self) -> Dict:
        """Get aggregate deal metrics"""
        try:
            total = await self.db.scalar(select(func.count()).select_from(Deal))
            active = await self.db.scalar(
                select(func.count()).select_from(Deal)
                .where(Deal.status == DealStatus.ACTIVE)
            )
            avg_price = await self.db.scalar(select(func.avg(Deal.price)))
            min_price = await self.db.scalar(select(func.min(Deal.price)))
            max_price = await self.db.scalar(select(func.max(Deal.price)))
            
            return {
                'total_deals': total,
                'active_deals': active,
                'avg_price': avg_price,
                'min_price': min_price,
                'max_price': max_price
            }
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal metrics: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_deal_metrics")

    async def update_deal_status(self, deal_id: str, status: DealStatus) -> Deal:
        """Update deal status"""
        deal = await self.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
        
        try:
            deal.status = status
            await self.db.commit()
            await self.db.refresh(deal)
            return deal
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update deal status: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "update_deal_status")

    async def bulk_create(self, deals: List[Dict]) -> List[Deal]:
        """Create multiple deals in a single transaction"""
        try:
            deal_objects = [Deal(**deal_data) for deal_data in deals]
            self.db.add_all(deal_objects)
            await self.db.commit()
            return deal_objects
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to bulk create deals: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal data in batch: {str(e)}")

    async def create_from_dict(self, data: Dict[str, Any]) -> Deal:
        """Create a Deal object from a dictionary representation.
        
        This is used primarily when reconstructing a Deal from cached data.
        
        Args:
            data: Dictionary containing Deal attributes
            
        Returns:
            Deal: Reconstructed Deal object
        """
        try:
            # Handle special fields that might need conversion
            if "id" in data and isinstance(data["id"], str):
                data["id"] = UUID(data["id"])
            if "user_id" in data and isinstance(data["user_id"], str):
                data["user_id"] = UUID(data["user_id"])
            if "goal_id" in data and isinstance(data["goal_id"], str) and data["goal_id"]:
                data["goal_id"] = UUID(data["goal_id"])
            if "market_id" in data and isinstance(data["market_id"], str):
                data["market_id"] = UUID(data["market_id"])
            
            # Handle datetime fields
            datetime_fields = ["found_at", "expires_at", "created_at", "updated_at"]
            for field in datetime_fields:
                if field in data and isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field])
            
            # Create Deal object 
            deal = Deal(**data)
            return deal
        except Exception as e:
            logger.error(f"Failed to create Deal from dict: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal data: {str(e)}")

    async def add_price_history(self, price_history: PriceHistory) -> PriceHistory:
        """
        Add price history entry for a deal
        
        Args:
            price_history: The PriceHistory object to add
            
        Returns:
            The created PriceHistory object
            
        Raises:
            DatabaseError: If there is a database error
        """
        try:
            self.db.add(price_history)
            await self.db.commit()
            await self.db.refresh(price_history)
            return price_history
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to add price history: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "add_price_history")

    async def get_by_url_and_goal(self, url: Optional[str], goal_id: UUID) -> Optional[Deal]:
        """Get deal by URL and goal_id combination."""
        if not url:
            return None
        
        try:
            result = await self.db.execute(
                select(Deal).where(
                    and_(
                        Deal.url == url,
                        Deal.goal_id == goal_id
                    )
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal by URL and goal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", "get_by_url_and_goal")
