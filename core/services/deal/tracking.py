"""Deal tracking service module.

This module provides deal tracking functionality for the AI Agentic Deals System.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from core.models.deal import Deal, DealStatus
from core.models.tracked_deal import TrackedDeal
from core.exceptions import DealNotFoundError, ServiceError
from core.utils.logger import get_logger

logger = get_logger(__name__)

class DealTrackingMixin:
    """Deal tracking functionality mixin for DealService.
    
    This mixin provides methods for tracking deals and retrieving tracked deals.
    It's intended to be used as a mixin for the DealService class.
    """
    
    async def track_deal(self, user_id: UUID, deal_id: UUID) -> TrackedDeal:
        """Start tracking a deal for a user.
        
        Args:
            user_id: The ID of the user who wants to track the deal
            deal_id: The ID of the deal to be tracked
            
        Returns:
            The created tracked deal entry
            
        Raises:
            DealNotFoundError: If the deal doesn't exist
            ServiceError: If tracking failed
        """
        try:
            # Check if the deal exists
            deal_query = select(Deal).where(Deal.id == deal_id)
            result = await self.db.execute(deal_query)
            deal = result.scalar_one_or_none()
            
            if not deal:
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            # Check if the deal is already being tracked
            existing_tracking_query = select(TrackedDeal).where(
                and_(
                    TrackedDeal.user_id == user_id,
                    TrackedDeal.deal_id == deal_id
                )
            )
            result = await self.db.execute(existing_tracking_query)
            existing_tracking = result.scalar_one_or_none()
            
            if existing_tracking:
                # Already tracking, just return the existing entry
                logger.info(f"User {user_id} is already tracking deal {deal_id}")
                return existing_tracking
                
            # Create new tracking entry
            tracked_deal = TrackedDeal(
                user_id=user_id,
                deal_id=deal_id,
                status=DealStatus.ACTIVE.value,
                tracking_started=datetime.utcnow()
            )
            
            self.db.add(tracked_deal)
            await self.db.commit()
            await self.db.refresh(tracked_deal)
            
            logger.info(f"User {user_id} started tracking deal {deal_id}")
            return tracked_deal
            
        except DealNotFoundError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error tracking deal {deal_id} for user {user_id}: {str(e)}")
            raise ServiceError(f"Failed to track deal: {str(e)}")
            
    async def stop_tracking_deal(self, user_id: UUID, deal_id: UUID) -> bool:
        """Stop tracking a deal for a user.
        
        Args:
            user_id: The ID of the user who wants to stop tracking
            deal_id: The ID of the deal to stop tracking
            
        Returns:
            True if tracking was stopped, False if deal wasn't being tracked
            
        Raises:
            ServiceError: If untracking failed
        """
        try:
            # Find the tracking entry
            tracking_query = select(TrackedDeal).where(
                and_(
                    TrackedDeal.user_id == user_id,
                    TrackedDeal.deal_id == deal_id
                )
            )
            result = await self.db.execute(tracking_query)
            tracked_deal = result.scalar_one_or_none()
            
            if not tracked_deal:
                logger.warning(f"User {user_id} tried to untrack deal {deal_id} which they weren't tracking")
                return False
                
            # Delete the tracking entry
            await self.db.delete(tracked_deal)
            await self.db.commit()
            
            logger.info(f"User {user_id} stopped tracking deal {deal_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error untracking deal {deal_id} for user {user_id}: {str(e)}")
            raise ServiceError(f"Failed to stop tracking deal: {str(e)}")
            
    async def get_tracked_deals(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get all deals tracked by a user.
        
        Args:
            user_id: The ID of the user whose tracked deals to retrieve
            
        Returns:
            List of tracked deals with deal information
            
        Raises:
            ServiceError: If retrieval failed
        """
        try:
            # Get all tracked deals for the user
            query = (
                select(TrackedDeal)
                .options(joinedload(TrackedDeal.deal))
                .where(TrackedDeal.user_id == user_id)
                .order_by(TrackedDeal.tracking_started.desc())
            )
            
            result = await self.db.execute(query)
            tracked_deals = result.unique().scalars().all()
            
            # Convert to response format
            tracked_deals_response = []
            for tracked_deal in tracked_deals:
                if not tracked_deal.deal:
                    logger.warning(f"Tracked deal {tracked_deal.id} references non-existent deal {tracked_deal.deal_id}")
                    continue
                    
                # Convert deal to response format
                deal_response = self._convert_to_response(tracked_deal.deal, user_id)
                
                # Add tracking info
                deal_response["tracking_info"] = {
                    "tracking_id": str(tracked_deal.id),
                    "tracking_started": tracked_deal.tracking_started.isoformat() if tracked_deal.tracking_started else None,
                    "last_checked": tracked_deal.last_checked.isoformat() if tracked_deal.last_checked else None,
                    "last_price": float(tracked_deal.last_price) if tracked_deal.last_price else None,
                    "is_favorite": tracked_deal.is_favorite,
                    "notify_on_price_drop": tracked_deal.notify_on_price_drop,
                    "notify_on_availability": tracked_deal.notify_on_availability,
                    "price_threshold": float(tracked_deal.price_threshold) if tracked_deal.price_threshold else None,
                    "tracking_status": tracked_deal.status
                }
                
                tracked_deals_response.append(deal_response)
                
            logger.info(f"Retrieved {len(tracked_deals_response)} tracked deals for user {user_id}")
            return tracked_deals_response
            
        except Exception as e:
            logger.error(f"Error retrieving tracked deals for user {user_id}: {str(e)}")
            raise ServiceError(f"Failed to retrieve tracked deals: {str(e)}") 