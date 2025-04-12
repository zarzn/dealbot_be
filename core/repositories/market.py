from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, join, text, and_, or_
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
import logging
from sqlalchemy.orm import selectinload
import os

from core.models.market import Market, MarketCreate, MarketUpdate
from core.models.enums import MarketType, MarketStatus, MarketCategory
from core.exceptions import (
    MarketNotFoundError,
    InvalidMarketDataError,
    DatabaseError
)
from core.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

# Repository for market operations
class MarketRepository(BaseRepository[Market]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Market)

    async def create(self, market_data: Dict) -> Market:
        """Create a new market"""
        try:
            market = Market(**market_data)
            self.db.add(market)
            await self.db.commit()
            await self.db.refresh(market)
            return market
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create market: {str(e)}")
            raise InvalidMarketDataError(
                market="unknown",
                reason=f"Invalid market data: {str(e)}",
                details={"error": str(e)}
            )

    async def get_by_id(self, market_id: str) -> Optional[Market]:
        """Get market by ID"""
        try:
            result = await self.db.execute(
                select(Market).where(Market.id == market_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_by_id",
                details={"market_id": market_id}
            )

    async def get_by_type(self, market_type: MarketType) -> Optional[Market]:
        result = await self.db.execute(
            select(Market).where(
                and_(
                    Market.type == market_type,
                    Market.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_truly_active_markets(self) -> List[Market]:
        """Get all active markets using a different approach."""
        try:
            # Direct approach without complex conditions
            all_markets = await self.db.execute(select(Market))
            markets = list(all_markets.scalars().all())
            
            # Filter in Python - only check is_active, not status
            active_markets = [m for m in markets if m.is_active]
            
            logger.info(f"Retrieved {len(active_markets)} truly active markets")
            return active_markets
        except Exception as e:
            logger.error(f"Error in get_truly_active_markets: {str(e)}")
            raise

    async def get_all_active(self) -> List[Market]:
        """Get all active markets."""
        # Use the new method instead
        return await self.get_truly_active_markets()

    async def get_all(self, page: int = 1, per_page: int = 20) -> List[Market]:
        """Get paginated list of markets"""
        try:
            result = await self.db.execute(
                select(Market)
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_all",
                details={"page": page, "per_page": per_page}
            )

    async def get_all_filtered(self, **filters) -> List[Market]:
        """Get filtered list of markets
        
        Args:
            **filters: Optional filters to apply, such as:
                - is_active: Filter by active status
                - type: Filter by market type
                - status: Filter by market status
                - name: Filter by name (contains)
                - category: Filter by category
        
        Returns:
            List[Market]: List of markets matching the filters
        """
        try:
            query = select(Market)
            conditions = []
            
            if "is_active" in filters:
                conditions.append(Market.is_active == filters["is_active"])
                
            if "type" in filters:
                conditions.append(Market.type == filters["type"])
                
            if "status" in filters:
                conditions.append(Market.status == filters["status"])
                
            if "name" in filters and filters["name"]:
                conditions.append(Market.name.ilike(f"%{filters['name']}%"))
                
            if "category" in filters:
                conditions.append(Market.category == filters["category"])
                
            if conditions:
                query = query.where(and_(*conditions))
                
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get filtered markets: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_all_filtered",
                details={"filters": filters}
            )

    async def get_by_category(self, category: MarketCategory) -> List[Market]:
        """Get markets by category"""
        try:
            result = await self.db.execute(
                select(Market).where(Market.category == category)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets by category: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_by_category",
                details={"category": category}
            )

    async def update(self, market_id: str, **kwargs) -> Market:
        """Update market data with keyword arguments
        
        Args:
            market_id: The ID of the market to update
            **kwargs: The market attributes to update
            
        Returns:
            Market: The updated market
            
        Raises:
            MarketNotFoundError: If the market doesn't exist
            InvalidMarketDataError: If the data is invalid
        """
        market = await self.get_by_id(market_id)
        if not market:
            raise MarketNotFoundError(f"Market {market_id} not found")
        
        try:
            for key, value in kwargs.items():
                setattr(market, key, value)
            await self.db.commit()
            await self.db.refresh(market)
            return market
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update market: {str(e)}")
            raise InvalidMarketDataError(
                market=str(market_id),
                reason=f"Invalid market data: {str(e)}",
                details={"error": str(e)}
            )

    async def delete(self, market_id: str) -> None:
        """Delete a market"""
        try:
            result = await self.db.execute(
                delete(Market).where(Market.id == market_id)
            )
            if result.rowcount == 0:
                raise MarketNotFoundError(f"Market {market_id} not found")
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to delete market: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="delete",
                details={"market_id": market_id}
            )

    async def get_active_markets(self) -> List[Market]:
        """Get all active markets"""
        # Use the new method
        return await self.get_truly_active_markets()

    async def update_market_stats(self, market_id: str, stats_data: Dict) -> Market:
        """Update market statistics"""
        market = await self.get_by_id(market_id)
        if not market:
            raise MarketNotFoundError(f"Market {market_id} not found")
        
        try:
            market.last_update = datetime.now(tz=datetime.UTC)
            market.stats = stats_data
            await self.db.commit()
            await self.db.refresh(market)
            return market
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update market stats: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="update_market_stats",
                details={"market_id": market_id}
            )

    async def get_market_performance(self, market_id: str, days: int = 30) -> List[Dict]:
        """Get market performance metrics"""
        try:
            market = await self.get_by_id(market_id)
            if not market:
                raise MarketNotFoundError(f"Market {market_id} not found")

            # Using a raw SQL query instead of ORM expressions
            # to avoid attribute errors with last_update and stats
            query = """
            SELECT 
                date_trunc('day', last_update) as date,
                stats->'performance' as performance,
                stats->'volume' as volume
            FROM 
                markets
            WHERE 
                id = :market_id
                AND last_update >= :cutoff_date
            GROUP BY 
                date_trunc('day', last_update)
            ORDER BY 
                date_trunc('day', last_update) DESC
            """
            
            cutoff_date = datetime.now(tz=datetime.UTC) - timedelta(days=days)
            result = await self.db.execute(
                text(query),
                {"market_id": market_id, "cutoff_date": cutoff_date}
            )
            return [dict(row) for row in result.all()]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market performance: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_market_performance",
                details={"market_id": market_id}
            )

    async def get_market_metrics(self) -> Dict:
        """Get aggregate market metrics"""
        try:
            # Use scalar() with a select statement that wraps the count function
            total_query = select(func.count(Market.id)).select_from(Market)
            total = await self.db.scalar(total_query)
            
            # For active markets count - only filter by is_active
            active_query = select(func.count(Market.id)).select_from(Market).where(Market.is_active == True)
            active = await self.db.scalar(active_query)
            
            # For category distribution
            categories_query = select(Market.category, func.count(Market.id)).select_from(Market).group_by(Market.category)
            categories_result = await self.db.execute(categories_query)
            
            return {
                'total_markets': total,
                'active_markets': active,
                'categories': dict(categories_result.all())
            }
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market metrics: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_market_metrics"
            )

    async def update_market_status(self, market_id: str, status: MarketStatus) -> Market:
        """Update market status"""
        market = await self.get_by_id(market_id)
        if not market:
            raise MarketNotFoundError(f"Market {market_id} not found")
        
        try:
            market.status = status
            market.last_status_update = datetime.now(tz=datetime.UTC)
            await self.db.commit()
            await self.db.refresh(market)
            return market
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to update market status: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="update_market_status",
                details={"market_id": market_id, "status": status}
            )

    async def get_markets_with_deals(self) -> List[Market]:
        """Get markets with their associated deals"""
        try:
            result = await self.db.execute(
                select(Market)
                .options(selectinload(Market.deals))
                .where(Market.is_active == True)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets with deals: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_markets_with_deals"
            )

    async def get_markets_by_performance(self, limit: int = 10) -> List[Market]:
        """Get top performing markets based on success rate and response time."""
        result = await self.db.execute(
            select(Market)
            .where(Market.is_active == True)
            .order_by(
                Market.success_rate.desc(),
                Market.avg_response_time.asc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_markets_by_status(self, status: MarketStatus) -> List[Market]:
        """Get markets by their operational status.
        
        Note: While this method filters by status, the preferred approach is to filter
        by is_active=True to determine market activity in the system.
        """
        result = await self.db.execute(
            select(Market)
            .where(
                and_(
                    Market.status == status,
                    Market.is_active == True
                )
            )
        )
        return list(result.scalars().all())

    async def get_markets_by_request_volume(self, min_requests: int = 1000) -> List[Market]:
        """Get markets with high request volume."""
        result = await self.db.execute(
            select(Market)
            .where(
                and_(
                    Market.is_active == True,
                    Market.total_requests >= min_requests
                )
            )
            .order_by(Market.total_requests.desc())
        )
        return list(result.scalars().all())

    async def get_markets_by_types(self, market_types: List[MarketType], only_active: bool = True) -> List[Market]:
        """Get markets matching any of the specified types.
        
        Args:
            market_types: List of MarketType enum values to filter by
            only_active: If True, only return active markets
            
        Returns:
            List[Market]: List of markets matching any of the specified types
        """
        try:
            # Convert enum values to strings for comparison
            type_values = [market_type.value.lower() for market_type in market_types]
            
            # Build the query
            query = select(Market)
            
            # Add conditions
            conditions = []
            conditions.append(Market.type.in_(type_values))
            
            if only_active:
                conditions.append(Market.is_active == True)
                
            if conditions:
                query = query.where(and_(*conditions))
                
            # Execute the query
            result = await self.db.execute(query)
            markets = list(result.scalars().all())
            
            logger.info(f"Retrieved {len(markets)} markets matching types: {type_values}")
            return markets
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets by types: {str(e)}")
            raise DatabaseError(
                message=f"Database error: {str(e)}",
                operation="get_markets_by_types",
                details={"market_types": [mt.value for mt in market_types]}
            ) 
