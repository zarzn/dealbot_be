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

# Import exceptions
from core.exceptions import (
    DatabaseError,
    DealNotFoundError,
    InvalidDealDataError
)

from core.utils.redis import get_redis_client

logger = logging.getLogger(__name__)

class DealRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Failed to execute search: {str(e)}")
            
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
        if filters.brands:
            query = query.where(Deal.brand.in_(filters.brands))
        if filters.condition:
            query = query.where(Deal.condition.in_(filters.condition))
        return query
        
    def apply_sorting(self, query: Any, sort_by: str):
        """Apply sorting to query."""
        sort_map = {
            "price_asc": Deal.price.asc(),
            "price_desc": Deal.price.desc(),
            "rating": Deal.rating.desc(),
            "expiry": Deal.expires_at.asc(),
            "relevance": Deal.deal_score.desc()
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
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_deal_scores(
        self,
        product_name: str,
        limit: int = 10
    ) -> List[float]:
        """Get historical deal scores for a product"""
        try:
            stmt = select(Deal.score).where(
                and_(
                    Deal.title.ilike(f"%{product_name}%"),
                    Deal.score.isnot(None)
                )
            ).order_by(Deal.created_at.desc()).limit(limit)
            
            result = await self.db.execute(stmt)
            return [float(row.score) for row in result.scalars().all()]
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal scores: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

    async def create_deal_score(
        self,
        product_name: str,
        score_data: Dict[str, Any]
    ) -> None:
        """Store deal score history"""
        try:
            stmt = text("""
                INSERT INTO deal_scores (
                    product_name,
                    score,
                    moving_average,
                    std_dev,
                    is_anomaly,
                    created_at
                ) VALUES (
                    :product_name,
                    :score,
                    :moving_average,
                    :std_dev,
                    :is_anomaly,
                    :created_at
                )
            """)
            
            await self.db.execute(
                stmt,
                {
                    "product_name": product_name,
                    "score": score_data["score"],
                    "moving_average": score_data["moving_average"],
                    "std_dev": score_data["std_dev"],
                    "is_anomaly": score_data["is_anomaly"],
                    "created_at": datetime.utcnow()
                }
            )
            await self.db.commit()
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal score: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal score data: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

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
