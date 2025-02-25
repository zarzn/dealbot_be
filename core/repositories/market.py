from typing import List, Optional, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, or_, delete
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
import logging
from sqlalchemy.orm import selectinload

from core.models.market import Market, MarketCreate, MarketUpdate
from core.models.enums import MarketType, MarketStatus, MarketCategory
from core.exceptions import (
    MarketNotFoundError,
    InvalidMarketDataError,
    DatabaseError
)

logger = logging.getLogger(__name__)

# Repository for market operations
class MarketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

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
            raise InvalidMarketDataError(f"Invalid market data: {str(e)}")

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
                operation="get_by_id",
                message=f"Database error: {str(e)}"
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

    async def get_all_active(self) -> List[Market]:
        result = await self.db.execute(
            select(Market).where(
                and_(
                    Market.is_active == True,
                    Market.status == MarketStatus.ACTIVE
                )
            )
        )
        return list(result.scalars().all())

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
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_by_category(self, category: MarketCategory) -> List[Market]:
        """Get markets by category"""
        try:
            result = await self.db.execute(
                select(Market).where(Market.category == category)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets by category: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise InvalidMarketDataError(f"Invalid market data: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_active_markets(self) -> List[Market]:
        """Get all active markets"""
        try:
            result = await self.db.execute(
                select(Market).where(Market.status == MarketStatus.ACTIVE)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active markets: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_market_performance(self, market_id: str, days: int = 30) -> List[Dict]:
        """Get market performance metrics"""
        try:
            market = await self.get_by_id(market_id)
            if not market:
                raise MarketNotFoundError(f"Market {market_id} not found")

            result = await self.db.execute(
                select(
                    func.date_trunc('day', Market.last_update).label('date'),
                    func.jsonb_path_query(Market.stats, '$.performance').label('performance'),
                    func.jsonb_path_query(Market.stats, '$.volume').label('volume')
                )
                .where(
                    and_(
                        Market.id == market_id,
                        Market.last_update >= datetime.now(tz=datetime.UTC) - timedelta(days=days)
                    )
                )
                .group_by(func.date_trunc('day', Market.last_update))
                .order_by(func.date_trunc('day', Market.last_update).desc())
            )
            return [dict(row) for row in result.all()]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market performance: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_market_metrics(self) -> Dict:
        """Get aggregate market metrics"""
        try:
            total = await self.db.scalar(select(func.count(Market.id)))
            active = await self.db.scalar(
                select(func.count(Market.id))
                .where(Market.status == MarketStatus.ACTIVE)
            )
            categories = await self.db.execute(
                select(Market.category, func.count(Market.id))
                .group_by(Market.category)
            )
            
            return {
                'total_markets': total,
                'active_markets': active,
                'categories': dict(categories.all())
            }
        except SQLAlchemyError as e:
            logger.error(f"Failed to get market metrics: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

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
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_markets_with_deals(self) -> List[Market]:
        """Get markets with their associated deals"""
        try:
            result = await self.db.execute(
                select(Market)
                .options(selectinload(Market.deals))
                .where(Market.status == MarketStatus.ACTIVE)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get markets with deals: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

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
        """Get markets by their operational status."""
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

    async def get_markets_with_high_error_rate(self, threshold: float = 0.1) -> List[Market]:
        """Get markets with error rate above threshold."""
        result = await self.db.execute(
            select(Market)
            .where(
                and_(
                    Market.is_active == True,
                    Market.success_rate < (1 - threshold)
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
