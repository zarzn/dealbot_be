from typing import List, Optional, Dict
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.exc import SQLAlchemyError
import logging

# Import models
from core.models import (
    Deal,
    DealStatus,
    Goal,
    DealScore,
    GoalStatus
)

# Import exceptions
from core.exceptions import (
    DatabaseError,
    DealNotFoundError,
    InvalidDealDataError
)

logger = logging.getLogger(__name__)

class DealRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, deal_data: Dict) -> Deal:
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

    async def get_by_id(self, deal_id: str) -> Optional[Deal]:
        """Get deal by ID"""
        try:
            result = await self.db.execute(
                select(Deal).where(Deal.id == deal_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

    async def search(self, query: str, limit: int = 10) -> List[Deal]:
        """Search deals by product name or description"""
        try:
            result = await self.db.execute(
                select(Deal)
                .where(
                    or_(
                        Deal.product_name.ilike(f"%{query}%"),
                        Deal.description.ilike(f"%{query}%")
                    )
                )
                .limit(limit)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to search deals: {str(e)}")
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

    async def get_price_history(self, product_name: str, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        try:
            result = await self.db.execute(
                select(
                    func.date_trunc('day', Deal.found_at).label('date'),
                    func.min(Deal.price).label('min_price'),
                    func.max(Deal.price).label('max_price'),
                    func.avg(Deal.price).label('avg_price')
                )
                .where(
                    and_(
                        Deal.product_name == product_name,
                        Deal.found_at >= datetime.now(tz=datetime.UTC) - timedelta(days=days)
                    )
                )
                .group_by(func.date_trunc('day', Deal.found_at))
                .order_by(func.date_trunc('day', Deal.found_at).desc())
            )
            return [dict(row) for row in result.all()]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get price history: {str(e)}")
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
            total = await self.db.scalar(select(func.count(Deal.id)))
            active = await self.db.scalar(
                select(func.count(Deal.id))
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

    async def delete(self, deal_id: str) -> None:
        """Delete a deal"""
        try:
            result = await self.db.execute(
                delete(Deal).where(Deal.id == deal_id)
            )
            if result.rowcount == 0:
                raise DealNotFoundError(f"Deal {deal_id} not found")
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to delete deal: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

    async def get_active_goals(self) -> List[Goal]:
        """Get active goals for deal monitoring"""
        try:
            result = await self.db.execute(
                select(Goal).where(Goal.status == GoalStatus.ACTIVE)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active goals: {str(e)}")
            raise DatabaseError(f"Database error: {str(e)}")

    async def create_deal_score(self, deal_id: UUID, score_data: Dict) -> DealScore:
        """Create a new deal score record"""
        try:
            deal_score = DealScore(
                deal_id=deal_id,
                score=score_data['score'],
                confidence=score_data.get('confidence', 1.0),
                metadata=score_data.get('metrics')
            )
            self.db.add(deal_score)
            await self.db.commit()
            await self.db.refresh(deal_score)
            return deal_score
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to create deal score: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal score data: {str(e)}")
