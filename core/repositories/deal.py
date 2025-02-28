from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete, desc, exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, Query
from sqlalchemy.sql import text
from redis.asyncio import Redis
import logging
import asyncio
import os

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
    InvalidDealDataError,
    ValidationError
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
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="create_deal")

    async def get_by_id(self, deal_id: UUID) -> Optional[Deal]:
        """Get deal by ID"""
        try:
            result = await self.db.execute(
                select(Deal).where(Deal.id == deal_id)
            )
            deal = result.scalars().first()
            
            if not deal:
                logger.warning(f"Deal with ID {deal_id} not found")
                return None
            
            return deal
        except Exception as e:
            logger.error(f"Failed to get deal by ID: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="get_by_id")

    async def update(self, deal_id: UUID, deal_data: DealUpdate) -> Deal:
        """Update deal"""
        try:
            # First check if the deal exists
            deal = await self.get_by_id(deal_id)
            if not deal:
                logger.warning(f"Deal with ID {deal_id} not found for update")
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            # For Pydantic v2 compatibility, handle both model_dump and dict methods
            # First convert to dict if it's a Pydantic model
            update_dict = {}
            if hasattr(deal_data, 'model_dump'):
                # Pydantic v2
                update_dict = deal_data.model_dump(exclude_unset=True)
            elif hasattr(deal_data, 'dict'):
                # Pydantic v1
                update_dict = deal_data.dict(exclude_unset=True)
            else:
                # Already a dict or similar
                update_dict = dict(deal_data)
            
            # Check if we have data to update
            if not update_dict:
                logger.warning(f"No fields to update for deal {deal_id}")
                return deal
            
            logger.debug(f"Updating deal {deal_id} with fields: {list(update_dict.keys())}")
            
            # Apply each update directly to the model
            for field, value in update_dict.items():
                logger.debug(f"Setting {field} = {value}")
                setattr(deal, field, value)
                
            # Update timestamp
            deal.updated_at = datetime.utcnow()
            
            # Commit changes
            await self.db.commit()
            await self.db.refresh(deal)
            
            logger.info(f"Updated deal {deal_id} successfully")
            return deal
        except DealNotFoundError:
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="update")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error updating deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="update")

    async def delete(self, deal_id: UUID) -> bool:
        """Delete deal"""
        try:
            deal = await self.get_by_id(deal_id)
            if not deal:
                logger.warning(f"Deal with ID {deal_id} not found for deletion")
                return False
                
            await self.db.delete(deal)
            await self.db.commit()
            logger.info(f"Deleted deal {deal_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="delete")

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
            raise DatabaseError(f"Failed to execute search: {str(e)}", operation="search_with_filters")
            
    def build_search_query(self, query: str):
        """Build base search query."""
        return select(Deal).where(
            or_(
                Deal.title.ilike(f"%{query}%"),
                Deal.description.ilike(f"%{query}%"),
                Deal.category.ilike(f"%{query}%")
            )
        ).where(Deal.status == DealStatus.ACTIVE)
        
    async def apply_filters(self, query, filters: Dict[str, Any]) -> Query:
        """Apply filters to the query based on criteria."""
        if not filters:
            return query
        
        if "title" in filters and filters["title"]:
            query = query.filter(Deal.title.ilike(f"%{filters['title']}%"))
        
        if "price_min" in filters and filters["price_min"] is not None:
            query = query.filter(Deal.price >= filters["price_min"])
        
        if "price_max" in filters and filters["price_max"] is not None:
            query = query.filter(Deal.price <= filters["price_max"])
        
        if "market" in filters and filters["market"]:
            query = query.filter(Deal.market_id == filters["market"])
        
        if "source" in filters and filters["source"]:
            query = query.filter(Deal.source == filters["source"])
        
        if "is_active" in filters:
            query = query.filter(Deal.is_active == filters["is_active"])
        
        return query
        
    async def apply_sorting(self, query, sort_by: str, sort_order: str) -> Query:
        """Apply sorting to the query."""
        # Map sort_by values to model attributes
        sort_map = {
            "price": Deal.price,
            "title": Deal.title,
            "created_at": Deal.created_at,
            # Removed references to non-existent attributes
        }
        
        # Default sort by created_at if sort_by not in map
        sort_attr = sort_map.get(sort_by, Deal.created_at)
        
        # Apply sort direction
        if sort_order.lower() == "desc":
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
        
        return query
        
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
            raise DatabaseError(f"Database error: {str(e)}", operation="get_price_history_by_name")

    async def get_deal_scores(
        self,
        deal_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get historical deal scores for a product."""
        try:
            query = (
                select(DealScore)
                .where(DealScore.deal_id == deal_id)
                .order_by(DealScore.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            scores = result.scalars().all()
            
            return [
                {
                    "id": str(score.id),
                    "score": score.score,
                    "confidence": score.confidence,
                    "timestamp": score.created_at.isoformat(),
                    "type": score.score_type,
                    "metadata": score.score_metadata
                }
                for score in scores
            ]
            
        except Exception as e:
            logger.error(f"Failed to get deal scores: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="get_deal_scores")

    async def create_deal_score(
        self, 
        deal_id: UUID, 
        score: float, 
        confidence: float = 1.0, 
        score_type: str = "ai", 
        score_metadata: Optional[Dict[str, Any]] = None
    ) -> DealScore:
        """Create a new deal score.
        
        Args:
            deal_id: The ID of the deal
            score: The score value
            confidence: How confident the score is
            score_type: Type of score (ai, user, system)
            score_metadata: Additional metadata about the score
            
        Returns:
            The created DealScore object
            
        Raises:
            DatabaseError: If there is a database error
        """
        try:
            # Create basic deal score data
            score_data = {
                'deal_id': deal_id,
                'score': score,
                'confidence': confidence,
                'score_type': score_type,
                'factors': {},  # Default empty dictionary for factors
            }
            
            # Add optional fields if provided
            if score_metadata:
                score_data['score_metadata'] = score_metadata
            
            # Create deal score object
            deal_score = DealScore(**score_data)
            
            self.db.add(deal_score)
            await self.db.commit()
            await self.db.refresh(deal_score)
            
            logger.info(f"Created deal score for deal {deal_id} with score {score}")
            return deal_score
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal score: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="create_deal_score")

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
            raise DatabaseError(f"Database error: {str(e)}", operation="get_active_goals")

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
            raise DatabaseError(f"Database error: {str(e)}", operation="get_active_deals")

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
            raise DatabaseError(f"Database error: {str(e)}", operation="get_deals_by_source")

    async def get_deal_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics about deals."""
        try:
            # Total number of deals
            total_count_query = select(func.count()).select_from(Deal)
            total_count = await self.db.scalar(total_count_query) or 0
            
            # Number of active deals
            active_count_query = select(func.count()).select_from(
                select(Deal).where(Deal.is_active == True).subquery()
            )
            active_count = await self.db.scalar(active_count_query) or 0
            
            # Average price
            avg_price_query = select(func.avg(Deal.price))
            avg_price = await self.db.scalar(avg_price_query) or 0
            
            # Price range
            min_price_query = select(func.min(Deal.price))
            min_price = await self.db.scalar(min_price_query) or 0
            
            max_price_query = select(func.max(Deal.price))
            max_price = await self.db.scalar(max_price_query) or 0
            
            # Deals by market distribution
            market_distribution_query = (
                select(Deal.market_id, func.count()).select_from(Deal)
                .group_by(Deal.market_id)
            )
            result = await self.db.execute(market_distribution_query)
            market_distribution = {str(market_id): count for market_id, count in result}
            
            return {
                "total_count": total_count,
                "active_count": active_count,
                "inactive_count": total_count - active_count,
                "avg_price": float(avg_price),
                "min_price": float(min_price),
                "max_price": float(max_price),
                "price_range": float(max_price) - float(min_price),
                "market_distribution": market_distribution
            }
            
        except Exception as e:
            logger.error(f"Failed to get deal metrics: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="get_deal_metrics")

    async def update_deal_status(self, deal_id: UUID, is_active: bool) -> bool:
        """Update deal active status."""
        try:
            deal = await self.get_by_id(deal_id)
            if not deal:
                return False
            
            deal.is_active = is_active
            await self.db.commit()
            
            logger.info(f"Updated deal {deal_id} status to {is_active}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update deal status: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="update_deal_status")

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
        Add a price history entry for a deal with guaranteed uniqueness.
        
        This method uses a robust retry mechanism to handle unique constraint violations
        and generates unique timestamps to ensure each entry can be added.
        
        In test environments, it can handle cases where the deal exists in the current
        transaction but not in the wider database context.
        """
        # Set a unique ID if not provided
        if not price_history.id:
            price_history.id = uuid4()
        
        # Create a unique timestamp with microsecond precision
        now = datetime.utcnow()
        # Generate a truly unique microsecond value based on UUID
        microseconds = (now.microsecond + uuid4().int % 1000) % 1000000
        unique_timestamp = now.replace(microsecond=microseconds)
        
        # Set timestamps if not already set
        if not price_history.created_at:
            price_history.created_at = unique_timestamp
        if not price_history.updated_at:
            price_history.updated_at = price_history.created_at
        
        # Maximum retries for unique constraint violations
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Add the price history entry to the database directly
                # Note: We bypass the normal check in test environments to avoid foreign key issues
                self.db.add(price_history)
                await self.db.flush()
                
                # If we get here, the operation succeeded
                logger.info(f"Added price history for deal {price_history.deal_id}")
                return price_history
                
            except Exception as e:
                await self.db.rollback()
                
                # Handle unique constraint violations
                if "uq_price_history_deal_time" in str(e):
                    logger.warning(f"Unique constraint violation for price history. Retrying with a new timestamp. Attempt {retry_count + 1}/{max_retries}")
                    retry_count += 1
                    
                    # Generate a new unique timestamp for retry
                    now = datetime.utcnow()
                    # Add retry count and random component to ensure uniqueness
                    microseconds = (now.microsecond + uuid4().int % 1000 + retry_count * 1000) % 1000000
                    price_history.created_at = now.replace(microsecond=microseconds)
                    price_history.updated_at = price_history.created_at
                    price_history.id = uuid4()  # Generate new ID as well
                    
                    # Short delay before retry
                    await asyncio.sleep(0.01 * retry_count)
                
                # Handle foreign key violations
                elif "ForeignKeyViolationError" in str(e) and "price_histories_deal_id_fkey" in str(e):
                    # Check if the deal exists in the current transaction
                    try:
                        # Check in the current transaction
                        check_query = select(Deal.id).where(Deal.id == price_history.deal_id)
                        check_result = await self.db.execute(check_query)
                        deal_exists_in_transaction = check_result.scalar_one_or_none() is not None
                        
                        # Check if we're in a test environment (based on settings or environment variable)
                        is_test_env = os.environ.get("TESTING", "false").lower() == "true"
                        
                        if deal_exists_in_transaction and is_test_env:
                            # In test environment, if the deal exists in the transaction but not in the wider
                            # database context, we should try to proceed anyway
                            logger.warning(f"Deal {price_history.deal_id} exists in transaction but not in global DB state. Retrying in test environment.")
                            retry_count += 1
                            
                            # Wait a bit and retry with a new ID
                            await asyncio.sleep(0.02)
                            price_history.id = uuid4()
                            
                        elif not deal_exists_in_transaction:
                            # Deal doesn't exist at all
                            logger.error(f"Deal {price_history.deal_id} not found when adding price history")
                            raise DealNotFoundError(f"Deal with ID {price_history.deal_id} not found")
                        else:
                            # Deal exists but we still have a foreign key issue
                            logger.warning(f"Deal exists but foreign key violation occurred. Retrying. Attempt {retry_count + 1}/{max_retries}")
                            retry_count += 1
                            
                            # Wait a bit and retry with a new ID
                            await asyncio.sleep(0.02)
                            # Generate a new unique ID and timestamp for retry
                            price_history.id = uuid4()
                            now = datetime.utcnow()
                            microseconds = (now.microsecond + uuid4().int % 1000 + retry_count * 1000) % 1000000
                            price_history.created_at = now.replace(microsecond=microseconds)
                            price_history.updated_at = price_history.created_at
                            
                            # Short delay before retry
                            await asyncio.sleep(0.02 * retry_count)
                    except Exception as check_e:
                        logger.error(f"Error checking deal existence: {str(check_e)}")
                        raise DatabaseError(f"Database error: {str(e)}", operation="add_price_history")
                else:
                    logger.error(f"Failed to add price history: {str(e)}")
                    raise DatabaseError(f"Database error: {str(e)}", operation="add_price_history")
            
        # If we've exhausted all retries
        logger.error(f"Failed to add price history after {max_retries} attempts")
        raise DatabaseError(f"Failed to add price history after {max_retries} attempts", operation="add_price_history")

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
            raise DatabaseError(f"Database error: {str(e)}", operation="get_by_url_and_goal")

    async def get(self, deal_id: Union[str, UUID]) -> Optional[Deal]:
        """Get a deal by ID."""
        try:
            if isinstance(deal_id, str):
                deal_id = UUID(deal_id)
            
            query = select(Deal).where(Deal.id == deal_id)
            result = await self.db.execute(query)
            deal = result.scalar_one_or_none()
            
            return deal
            
        except ValueError as e:
            # Invalid UUID format
            logger.error(f"Invalid deal ID format: {deal_id}")
            raise ValidationError(f"Invalid deal ID format: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="get_deal")

    async def find_by_external_id(self, external_id: str, market_id: UUID) -> Optional[Deal]:
        """Find a deal by its external ID and market ID."""
        try:
            query = (
                select(Deal)
                .where(Deal.external_id == external_id)
                .where(Deal.market_id == market_id)
            )
            
            result = await self.db.execute(query)
            deal = result.scalar_one_or_none()
            
            return deal
            
        except Exception as e:
            logger.error(f"Failed to find deal by external ID: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="find_by_external_id")

    async def search(
        self,
        search_term: str,
        market_id: Optional[UUID] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Deal], int]:
        """Search for deals by term."""
        try:
            query = select(Deal).where(
                Deal.title.ilike(f"%{search_term}%")
            )
            
            if market_id:
                query = query.where(Deal.market_id == market_id)
            
            # Get total count for pagination
            count_query = select(func.count()).select_from(query.subquery())
            total = await self.db.scalar(count_query) or 0
            
            # Apply limit and offset for pagination
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            deals = result.scalars().all()
            
            return deals, total
            
        except Exception as e:
            logger.error(f"Failed to search deals: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="search_deals")

    async def get_price_history(
        self,
        deal_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get price history for a deal."""
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = (
                select(PriceHistory)
                .where(PriceHistory.deal_id == deal_id)
                .where(PriceHistory.created_at >= cutoff_date)
                .order_by(PriceHistory.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            history = result.scalars().all()
            
            return [
                {
                    "id": str(entry.id),
                    "price": float(entry.price),
                    "currency": entry.currency,
                    "source": entry.source,
                    "timestamp": entry.created_at.isoformat(),
                    "meta_data": entry.meta_data
                }
                for entry in history
            ]
            
        except Exception as e:
            logger.error(f"Failed to get price history: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}", operation="get_price_history")

    async def exists(self, deal_id: UUID) -> bool:
        """
        Check if a deal with the given ID exists in the database.
        
        Args:
            deal_id: The UUID of the deal to check
            
        Returns:
            bool: True if the deal exists, False otherwise
        """
        try:
            query = select(exists().where(Deal.id == deal_id))
            result = await self.db.execute(query)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error checking if deal {deal_id} exists: {str(e)}")
            return False
