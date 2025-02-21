"""Price prediction repository."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.models.price_prediction import PricePrediction
from core.repositories.base import BaseRepository
from core.utils.logger import get_logger

logger = get_logger(__name__)

class PricePredictionRepository(BaseRepository[PricePrediction]):
    """Repository for price predictions."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with session."""
        super().__init__(db=db, model=PricePrediction)

    async def get_by_deal(
        self,
        deal_id: UUID,
        limit: int = 10
    ) -> List[PricePrediction]:
        """Get predictions for a deal."""
        try:
            query = (
                select(self.model)
                .where(self.model.deal_id == deal_id)
                .order_by(desc(self.model.created_at))
                .limit(limit)
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting predictions for deal {deal_id}: {str(e)}")
            return []

    async def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[PricePrediction]:
        """Get predictions for a user."""
        try:
            query = (
                select(self.model)
                .where(self.model.user_id == user_id)
                .order_by(desc(self.model.created_at))
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting predictions for user {user_id}: {str(e)}")
            return []

    async def get_recent_predictions(
        self,
        deal_id: UUID,
        days: int = 7
    ) -> List[PricePrediction]:
        """Get recent predictions for a deal."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = (
                select(self.model)
                .where(
                    and_(
                        self.model.deal_id == deal_id,
                        self.model.created_at >= cutoff_date
                    )
                )
                .order_by(desc(self.model.created_at))
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting recent predictions for deal {deal_id}: {str(e)}")
            return []

    async def get_model_performance(
        self,
        model_name: str,
        limit: int = 100
    ) -> List[PricePrediction]:
        """Get predictions for model performance analysis."""
        try:
            query = (
                select(self.model)
                .where(self.model.model_name == model_name)
                .order_by(desc(self.model.created_at))
                .limit(limit)
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting performance for model {model_name}: {str(e)}")
            return []

    async def delete_old_predictions(
        self,
        days: int = 30
    ) -> int:
        """Delete predictions older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = (
                select(self.model)
                .where(self.model.created_at < cutoff_date)
            )
            result = await self.db.execute(query)
            old_predictions = result.scalars().all()
            
            for prediction in old_predictions:
                await self.db.delete(prediction)
            
            await self.db.commit()
            return len(old_predictions)
        except Exception as e:
            logger.error(f"Error deleting old predictions: {str(e)}")
            await self.db.rollback()
            return 0 