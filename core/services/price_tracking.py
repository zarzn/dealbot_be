"""Price tracking service for real-time price monitoring."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.models.price_tracking import (
    PricePointCreate,
    PricePointResponse,
    PriceTrackerCreate,
    PriceTrackerResponse,
    PriceStatistics,
    PricePoint,
    PriceTracker
)
from core.models.deal import Deal
from core.models.user import User
from core.services.base import BaseService
from core.exceptions import (
    PriceTrackingError,
    NotFoundError,
    ValidationError,
    DatabaseError,
    EntityNotFoundError
)
from core.services.notifications import NotificationService
from core.utils.redis import get_redis_client, Redis
from core.utils.logger import get_logger
from core.integrations.markets.base.market_base import MarketBase

logger = get_logger(__name__)

class PriceTrackingService:
    """Service for tracking and analyzing price changes."""

    def __init__(
        self,
        session: AsyncSession,
        notification_service: Optional[NotificationService] = None,
        redis_client: Optional[Redis] = None
    ):
        self.session = session
        self.notification_service = notification_service or NotificationService()
        self._redis_client = redis_client
        self._market_integrations: Dict[str, MarketBase] = {}

    async def _get_redis(self) -> Redis:
        """Get Redis client instance."""
        if not self._redis_client:
            self._redis_client = await get_redis_client()
        return self._redis_client

    async def create_tracker(
        self,
        tracker_data: PriceTrackerCreate,
        user_id: UUID
    ) -> PriceTrackerResponse:
        """Create a new price tracker."""
        try:
            # Get deal to verify existence and get initial price
            deal = await self._get_deal(tracker_data.deal_id)
            
            # Create tracker
            tracker = PriceTracker(
                deal_id=tracker_data.deal_id,
                user_id=user_id,
                initial_price=deal.price,
                threshold_price=tracker_data.threshold_price,
                check_interval=tracker_data.check_interval,
                notification_settings=tracker_data.notification_settings,
                meta_data=tracker_data.meta_data
            )
            
            self.session.add(tracker)
            await self.session.commit()
            await self.session.refresh(tracker)
            
            # Start tracking in background
            await self._start_tracking(tracker.id)
            
            return PriceTrackerResponse.model_validate(tracker)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating price tracker: {str(e)}")
            raise PriceTrackingError(f"Failed to create tracker: {str(e)}")

    async def get_tracker(
        self,
        tracker_id: int,
        user_id: UUID
    ) -> Optional[PriceTrackerResponse]:
        """Get a price tracker by ID."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                return None
                
            return PriceTrackerResponse.model_validate(tracker)
            
        except Exception as e:
            logger.error(f"Error getting price tracker: {str(e)}")
            raise PriceTrackingError(f"Failed to get tracker: {str(e)}")

    async def list_trackers(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[PriceTrackerResponse]:
        """List all price trackers for a user."""
        try:
            query = (
                select(PriceTracker)
                .where(PriceTracker.user_id == user_id)
                .offset(skip)
                .limit(limit)
                .options(joinedload(PriceTracker.deal))
            )
            
            result = await self.session.execute(query)
            trackers = result.scalars().all()
            
            return [PriceTrackerResponse.model_validate(t) for t in trackers]
            
        except Exception as e:
            logger.error(f"Error listing price trackers: {str(e)}")
            raise PriceTrackingError(f"Failed to list trackers: {str(e)}")

    async def update_tracker(
        self,
        tracker_id: int,
        user_id: UUID,
        update_data: PriceTrackerCreate
    ) -> Optional[PriceTrackerResponse]:
        """Update a price tracker."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                return None
                
            # Update fields
            for field, value in update_data.model_dump(exclude_unset=True).items():
                setattr(tracker, field, value)
                
            await self.session.commit()
            await self.session.refresh(tracker)
            
            return PriceTrackerResponse.model_validate(tracker)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating price tracker: {str(e)}")
            raise PriceTrackingError(f"Failed to update tracker: {str(e)}")

    async def delete_tracker(
        self,
        tracker_id: int,
        user_id: UUID
    ) -> bool:
        """Delete a price tracker."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                return False
                
            await self.session.delete(tracker)
            await self.session.commit()
            
            # Stop tracking in background
            await self._stop_tracking(tracker_id)
            
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting price tracker: {str(e)}")
            raise PriceTrackingError(f"Failed to delete tracker: {str(e)}")

    async def get_price_history(
        self,
        tracker_id: int,
        user_id: UUID,
        limit: int = 100
    ) -> List[PricePointResponse]:
        """Get price history for a tracker."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                return []
                
            query = (
                select(PricePoint)
                .where(PricePoint.deal_id == tracker.deal_id)
                .order_by(PricePoint.timestamp.desc())
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            points = result.scalars().all()
            
            return [PricePointResponse.model_validate(p) for p in points]
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise PriceTrackingError(f"Failed to get price history: {str(e)}")

    async def add_price_point(
        self,
        tracker_id: int,
        user_id: UUID,
        price_point: PricePointCreate
    ) -> PricePointResponse:
        """Add a new price point for a tracker."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                raise PriceTrackingError("Tracker not found")
                
            point = PricePoint(
                deal_id=tracker.deal_id,
                price=price_point.price,
                currency=price_point.currency,
                source=price_point.source,
                meta_data=price_point.meta_data
            )
            
            self.session.add(point)
            await self.session.commit()
            await self.session.refresh(point)
            
            # Check price thresholds
            await self._check_price_thresholds(tracker, point.price)
            
            return PricePointResponse.model_validate(point)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error adding price point: {str(e)}")
            raise PriceTrackingError(f"Failed to add price point: {str(e)}")

    async def get_price_stats(
        self,
        tracker_id: int,
        user_id: UUID
    ) -> PriceStatistics:
        """Get price statistics for a tracker."""
        try:
            tracker = await self._get_tracker(tracker_id, user_id)
            if not tracker:
                raise PriceTrackingError("Tracker not found")
                
            # Get price history
            query = (
                select(PricePoint)
                .where(PricePoint.deal_id == tracker.deal_id)
                .order_by(PricePoint.timestamp.desc())
            )
            
            result = await self.session.execute(query)
            points = result.scalars().all()
            
            if not points:
                raise PriceTrackingError("No price history available")
                
            prices = [p.price for p in points]
            
            return PriceStatistics(
                min_price=min(prices),
                max_price=max(prices),
                avg_price=sum(prices) / len(prices),
                median_price=sorted(prices)[len(prices) // 2],
                price_volatility=self._calculate_volatility(prices),
                total_points=len(points),
                time_range=f"{(points[0].timestamp - points[-1].timestamp).days} days",
                last_update=points[0].timestamp,
                trend=self._determine_trend(prices),
                meta_data={
                    'first_price': prices[-1],
                    'last_price': prices[0],
                    'price_change': prices[0] - prices[-1],
                    'price_change_percent': ((prices[0] - prices[-1]) / prices[-1]) * 100
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting price statistics: {str(e)}")
            raise PriceTrackingError(f"Failed to get price statistics: {str(e)}")

    async def _get_deal(self, deal_id: UUID) -> Deal:
        """Get a deal by ID."""
        query = select(Deal).where(Deal.id == deal_id)
        result = await self.session.execute(query)
        deal = result.scalar_one_or_none()
        
        if not deal:
            raise PriceTrackingError("Deal not found")
            
        return deal

    async def _get_tracker(
        self,
        tracker_id: int,
        user_id: UUID
    ) -> Optional[PriceTracker]:
        """Get a price tracker by ID and user ID."""
        query = (
            select(PriceTracker)
            .where(
                and_(
                    PriceTracker.id == tracker_id,
                    PriceTracker.user_id == user_id
                )
            )
            .options(joinedload(PriceTracker.deal))
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _start_tracking(self, tracker_id: int):
        """Start tracking price changes in background."""
        # Implementation will be added with background tasks
        pass

    async def _stop_tracking(self, tracker_id: int):
        """Stop tracking price changes in background."""
        # Implementation will be added with background tasks
        pass

    async def _check_price_thresholds(
        self,
        tracker: PriceTracker,
        current_price: Decimal
    ):
        """Check if price thresholds have been reached."""
        if not tracker.threshold_price:
            return
            
        if current_price <= tracker.threshold_price:
            await self.notification_service.send_notification({
                'type': 'price_threshold_reached',
                'user_id': tracker.user_id,
                'deal_id': tracker.deal_id,
                'tracker_id': tracker.id,
                'threshold_price': float(tracker.threshold_price),
                'current_price': float(current_price),
                'timestamp': datetime.utcnow().isoformat()
            })

    def _calculate_volatility(self, prices: List[Decimal]) -> float:
        """Calculate price volatility."""
        if len(prices) < 2:
            return 0.0
            
        price_changes = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(1, len(prices))
        ]
        
        return float(sum(abs(pc) for pc in price_changes) / len(price_changes))

    def _determine_trend(self, prices: List[Decimal]) -> str:
        """Determine price trend direction."""
        if len(prices) < 2:
            return "stable"
            
        first, last = prices[-1], prices[0]
        change_percent = ((last - first) / first) * 100
        
        if change_percent > 5:
            return "increasing"
        elif change_percent < -5:
            return "decreasing"
        else:
            return "stable" 
