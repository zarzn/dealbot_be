from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, Query
from sqlalchemy import func, and_, or_
import logging

from core.models.deal import Deal
from core.models.goal import Goal
from core.models.deal_score import DealScore
from core.exceptions import (
    DealNotFoundError,
    InvalidDealDataError,
    ExternalServiceError
)

logger = logging.getLogger(__name__)

class DealRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, deal_data: Dict) -> Deal:
        """Create a new deal"""
        try:
            deal = Deal(**deal_data)
            self.db.add(deal)
            self.db.commit()
            self.db.refresh(deal)
            return deal
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create deal: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal data: {str(e)}")

    def get_by_id(self, deal_id: str) -> Optional[Deal]:
        """Get deal by ID"""
        return self.db.query(Deal).filter(Deal.id == deal_id).first()

    def search(self, query: str, limit: int = 10) -> List[Deal]:
        """Search deals by product name or description"""
        return (
            self.db.query(Deal)
            .filter(
                or_(
                    Deal.product_name.ilike(f"%{query}%"),
                    Deal.description.ilike(f"%{query}%")
                )
            )
            .limit(limit)
            .all()
        )

    def bulk_create(self, deals: List[Dict]) -> List[Deal]:
        """Create multiple deals in a single transaction"""
        try:
            deal_objects = [Deal(**deal_data) for deal_data in deals]
            self.db.bulk_save_objects(deal_objects)
            self.db.commit()
            return deal_objects
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to bulk create deals: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal data in batch: {str(e)}")

    def get_price_history(self, product_name: str, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        return (
            self.db.query(
                func.date_trunc('day', Deal.found_at).label('date'),
                func.min(Deal.price).label('min_price'),
                func.max(Deal.price).label('max_price'),
                func.avg(Deal.price).label('avg_price')
            )
            .filter(
                and_(
                    Deal.product_name == product_name,
                    Deal.found_at >= datetime.now() - timedelta(days=days)
                )
            )
            .group_by(func.date_trunc('day', Deal.found_at))
            .order_by(func.date_trunc('day', Deal.found_at).desc())
            .all()
        )

    def get_active_deals(self, page: int = 1, per_page: int = 20) -> List[Deal]:
        """Get paginated list of active deals"""
        return (
            self.db.query(Deal)
            .filter(Deal.status == 'active')
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

    def get_deals_by_source(self, source: str, limit: int = 100) -> List[Deal]:
        """Get deals by source with limit"""
        return (
            self.db.query(Deal)
            .filter(Deal.source == source)
            .limit(limit)
            .all()
        )

    def get_deal_metrics(self) -> Dict:
        """Get aggregate deal metrics"""
        return {
            'total_deals': self.db.query(func.count(Deal.id)).scalar(),
            'active_deals': self.db.query(func.count(Deal.id))
                             .filter(Deal.status == 'active')
                             .scalar(),
            'avg_price': self.db.query(func.avg(Deal.price)).scalar(),
            'min_price': self.db.query(func.min(Deal.price)).scalar(),
            'max_price': self.db.query(func.max(Deal.price)).scalar()
        }

    def update_deal_status(self, deal_id: str, status: str) -> Deal:
        """Update deal status"""
        deal = self.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
        
        deal.status = status
        self.db.commit()
        self.db.refresh(deal)
        return deal

    def delete(self, deal_id: str) -> None:
        """Delete a deal"""
        deal = self.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
        
        self.db.delete(deal)
        self.db.commit()

    def get_active_goals(self) -> List[Dict]:
        """Get active goals for deal monitoring"""
        return (
            self.db.query(Goal)
            .filter(Goal.status == 'active')
            .all()
        )

    def get_deal_scores(self, product_name: str) -> List[float]:
        """Get historical scores for a product"""
        return (
            self.db.query(Deal.score)
            .filter(Deal.product_name == product_name)
            .order_by(Deal.found_at.desc())
            .all()
        )

    def create_deal_score(self, product_name: str, score_data: Dict) -> None:
        """Create a new deal score record"""
        try:
            deal_score = DealScore(
                product_name=product_name,
                score=score_data['score'],
                moving_average=score_data['moving_average'],
                std_dev=score_data['std_dev'],
                is_anomaly=score_data['is_anomaly']
            )
            self.db.add(deal_score)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create deal score: {str(e)}")
            raise InvalidDealDataError(f"Invalid deal score data: {str(e)}")
