"""Flash deals module.

This module provides functionality for handling flash deals and time-sensitive offers.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timedelta

from core.exceptions import (
    DealNotFoundError,
    RateLimitExceededError,
    DealExpirationError
)
from core.models.enums import DealStatus

logger = logging.getLogger(__name__)

# Constants
FLASH_DEAL_TTL = 3600 * 24  # 24 hours in seconds
FLASH_DEAL_SCORE_THRESHOLD = 8.5  # Minimum score for flash deals
MAX_ACTIVE_FLASH_DEALS = 100  # Maximum number of active flash deals in the system
FLASH_DEAL_REFRESH_INTERVAL = 900  # 15 minutes in seconds

async def get_flash_deals(
    self,
    user_id: Optional[UUID] = None,
    category: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    include_expired: bool = False
) -> Dict[str, Any]:
    """Get current flash deals with pagination.
    
    Args:
        user_id: Optional user ID to filter deals
        category: Optional category to filter deals
        limit: Maximum number of deals to return
        offset: Number of deals to skip
        include_expired: Whether to include expired flash deals
        
    Returns:
        Dictionary containing flash deals and pagination info
        
    Raises:
        RateLimitExceededError: If rate limit is exceeded
    """
    try:
        # Get current timestamp
        now = datetime.utcnow()
        
        # Build pipeline for Redis
        pipeline = self._redis_client.pipeline()
        
        # Get all flash deal IDs from sorted set
        pipeline.zrange("flash_deals", 0, -1, withscores=True)
        
        # Get flash deals count
        pipeline.zcard("flash_deals")
        
        # Execute pipeline
        results = await pipeline.execute()
        deal_ids_with_scores, total_count = results
        
        # Filter expired deals if needed
        if not include_expired:
            # Filter deals by expiration time
            deal_ids_with_scores = [
                (deal_id, score) for deal_id, score in deal_ids_with_scores
                if score > now.timestamp()
            ]
            
        # Apply pagination
        paginated_deal_ids = deal_ids_with_scores[offset:offset+limit]
        
        # If no flash deals, return empty results
        if not paginated_deal_ids:
            return {
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False
            }
            
        # Get deal IDs from paginated results
        deal_ids = [UUID(deal_id.decode("utf-8")) for deal_id, _ in paginated_deal_ids]
        
        # Get deals from database
        deals = await self._repository.get_by_ids(deal_ids)
        
        # Filter by user_id if provided
        if user_id:
            deals = [deal for deal in deals if deal.user_id == user_id]
            
        # Filter by category if provided
        if category:
            deals = [deal for deal in deals if deal.category and category.lower() in deal.category.lower()]
            
        # Sort deals by score (descending)
        deals.sort(key=lambda d: getattr(d, "ai_score", 0), reverse=True)
        
        # Build response
        return {
            "results": [self._serialize_flash_deal(deal) for deal in deals],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting flash deals: {str(e)}")
        raise

async def create_flash_deal(
    self,
    deal_id: UUID,
    expires_at: Optional[datetime] = None,
    score: Optional[float] = None,
    notify_users: bool = True
) -> Dict[str, Any]:
    """Create a flash deal from an existing deal.
    
    Args:
        deal_id: The ID of the deal to convert to flash deal
        expires_at: Optional expiration time, defaults to 24 hours
        score: Optional AI score to assign
        notify_users: Whether to notify users about this flash deal
        
    Returns:
        Dictionary with flash deal data
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Set expiration if not provided
        if not expires_at:
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
        # Calculate score if not provided
        if not score:
            analysis_result = await self._analyze_deal(deal.id)
            score = analysis_result.get("ai_score", 0)
            
        # Check if score meets threshold
        if score < FLASH_DEAL_SCORE_THRESHOLD:
            logger.warning(f"Deal {deal_id} score {score} is below threshold {FLASH_DEAL_SCORE_THRESHOLD}")
            return {
                "status": "rejected",
                "reason": "Score below threshold",
                "deal_id": str(deal_id),
                "score": score
            }
            
        # Update deal in database to mark as flash deal
        update_data = {
            "is_flash_deal": True,
            "flash_deal_expires_at": expires_at,
            "ai_score": score
        }
        
        # Add to flash deals in Redis
        expiration_timestamp = expires_at.timestamp()
        await self._redis_client.zadd("flash_deals", {str(deal_id): expiration_timestamp})
        
        # Set TTL for flash deal in Redis
        ttl = int((expires_at - datetime.utcnow()).total_seconds())
        
        # Store score in Redis
        await self._redis_client.set(f"flash_deal:{deal_id}:score", str(score), ex=ttl)
        
        # Update deal in database
        updated_deal = await self._repository.update(deal_id, update_data)
        
        # Notify users if requested
        if notify_users:
            asyncio.create_task(self._notify_users_of_flash_deal(deal_id))
            
        # Return flash deal data
        return {
            "status": "created",
            "deal_id": str(deal_id),
            "expires_at": expires_at.isoformat(),
            "score": score,
            "title": updated_deal.title,
            "price": str(updated_deal.price),
            "original_price": str(updated_deal.original_price) if updated_deal.original_price else None,
            "url": updated_deal.url,
            "image_url": updated_deal.image_url,
            "category": updated_deal.category
        }
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error creating flash deal for {deal_id}: {str(e)}")
        raise DealNotFoundError(f"Failed to create flash deal: {str(e)}")

async def extend_flash_deal(
    self,
    deal_id: UUID,
    extension_hours: int = 24
) -> Dict[str, Any]:
    """Extend expiration of an existing flash deal.
    
    Args:
        deal_id: The ID of the flash deal to extend
        extension_hours: Number of hours to extend by
        
    Returns:
        Dictionary with updated flash deal data
        
    Raises:
        DealNotFoundError: If flash deal not found
        DealExpirationError: If flash deal already expired
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Check if it's a flash deal
        if not getattr(deal, "is_flash_deal", False):
            raise DealNotFoundError(f"Deal {deal_id} is not a flash deal")
            
        # Check if deal has flash_deal_expires_at
        if not getattr(deal, "flash_deal_expires_at", None):
            raise DealNotFoundError(f"Deal {deal_id} has no flash deal expiration")
            
        # Check if already expired
        now = datetime.utcnow()
        if deal.flash_deal_expires_at < now:
            raise DealExpirationError(f"Flash deal {deal_id} already expired")
            
        # Calculate new expiration
        new_expiration = deal.flash_deal_expires_at + timedelta(hours=extension_hours)
        
        # Update expiration in Redis
        new_expiration_timestamp = new_expiration.timestamp()
        await self._redis_client.zadd("flash_deals", {str(deal_id): new_expiration_timestamp})
        
        # Update TTL for score in Redis
        ttl = int((new_expiration - now).total_seconds())
        await self._redis_client.expire(f"flash_deal:{deal_id}:score", ttl)
        
        # Update deal in database
        update_data = {
            "flash_deal_expires_at": new_expiration
        }
        updated_deal = await self._repository.update(deal_id, update_data)
        
        # Return updated flash deal data
        return {
            "status": "extended",
            "deal_id": str(deal_id),
            "expires_at": new_expiration.isoformat(),
            "extension_hours": extension_hours,
            "title": updated_deal.title
        }
        
    except (DealNotFoundError, DealExpirationError):
        raise
    except Exception as e:
        logger.error(f"Error extending flash deal {deal_id}: {str(e)}")
        raise DealNotFoundError(f"Failed to extend flash deal: {str(e)}")

async def remove_flash_deal(
    self,
    deal_id: UUID
) -> Dict[str, Any]:
    """Remove flash deal status from a deal.
    
    Args:
        deal_id: The ID of the flash deal to remove
        
    Returns:
        Dictionary with removal status
        
    Raises:
        DealNotFoundError: If flash deal not found
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Check if it's a flash deal
        if not getattr(deal, "is_flash_deal", False):
            raise DealNotFoundError(f"Deal {deal_id} is not a flash deal")
            
        # Remove from flash deals in Redis
        await self._redis_client.zrem("flash_deals", str(deal_id))
        
        # Remove score from Redis
        await self._redis_client.delete(f"flash_deal:{deal_id}:score")
        
        # Update deal in database
        update_data = {
            "is_flash_deal": False,
            "flash_deal_expires_at": None
        }
        await self._repository.update(deal_id, update_data)
        
        return {
            "status": "removed",
            "deal_id": str(deal_id)
        }
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error removing flash deal {deal_id}: {str(e)}")
        raise DealNotFoundError(f"Failed to remove flash deal: {str(e)}")

async def _cleanup_expired_flash_deals(self) -> int:
    """Clean up expired flash deals.
    
    Returns:
        Number of expired flash deals removed
    """
    try:
        # Get current timestamp
        now = datetime.utcnow().timestamp()
        
        # Remove expired flash deals from sorted set
        expired_count = await self._redis_client.zremrangebyscore("flash_deals", 0, now)
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired flash deals")
            
        return expired_count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired flash deals: {str(e)}")
        return 0

async def _find_potential_flash_deals(
    self,
    count: int = 10,
    min_score: float = FLASH_DEAL_SCORE_THRESHOLD
) -> List[Dict[str, Any]]:
    """Find potential deals that could be promoted to flash deals.
    
    Args:
        count: Number of potential flash deals to find
        min_score: Minimum AI score threshold
        
    Returns:
        List of potential flash deals
    """
    try:
        # Get recent deals with high scores
        deals = await self._repository.get_deals(
            limit=50,  # Get more deals to filter
            status=DealStatus.ACTIVE.value,
            order_by="ai_score",
            order="desc"
        )
        
        # Filter deals that are not already flash deals and meet score threshold
        potential_deals = []
        for deal in deals:
            # Skip existing flash deals
            if getattr(deal, "is_flash_deal", False):
                continue
                
            # Get or calculate score
            score = getattr(deal, "ai_score", None)
            if score is None:
                # Analyze deal to get score
                analysis_result = await self._analyze_deal(deal.id)
                score = analysis_result.get("ai_score", 0)
                
            # Check if meets threshold
            if score >= min_score:
                potential_deals.append({
                    "deal_id": deal.id,
                    "title": deal.title,
                    "price": deal.price,
                    "original_price": deal.original_price,
                    "url": deal.url,
                    "image_url": deal.image_url,
                    "category": deal.category,
                    "score": score
                })
                
            # Break if we have enough potential deals
            if len(potential_deals) >= count:
                break
                
        return potential_deals
        
    except Exception as e:
        logger.error(f"Error finding potential flash deals: {str(e)}")
        return []

async def _notify_users_of_flash_deal(self, deal_id: UUID) -> None:
    """Notify relevant users about a new flash deal.
    
    Args:
        deal_id: The ID of the flash deal
    """
    try:
        # Get deal details
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Cannot notify users of flash deal {deal_id}: deal not found")
            return
            
        # Get users who might be interested in this deal
        interested_users = await self._find_interested_users(deal)
        
        if not interested_users:
            logger.info(f"No users found interested in flash deal {deal_id}")
            return
            
        # Create notification data
        notification_data = {
            "type": "flash_deal",
            "deal_id": str(deal_id),
            "title": deal.title,
            "price": str(deal.price),
            "image_url": deal.image_url,
            "url": deal.url,
            "expires_at": deal.flash_deal_expires_at.isoformat() if deal.flash_deal_expires_at else None
        }
        
        # Send notifications
        for user_id in interested_users:
            asyncio.create_task(self._notification_service.send_notification(
                user_id=user_id,
                notification_type="flash_deal",
                data=notification_data
            ))
            
        logger.info(f"Notified {len(interested_users)} users about flash deal {deal_id}")
        
    except Exception as e:
        logger.error(f"Error notifying users of flash deal {deal_id}: {str(e)}")

async def _find_interested_users(self, deal) -> List[UUID]:
    """Find users who might be interested in a deal.
    
    Args:
        deal: Deal object
        
    Returns:
        List of user IDs
    """
    try:
        interested_users = set()
        
        # Users who have viewed similar deals
        if deal.category:
            category_watchers = await self._repository.get_category_watchers(deal.category)
            interested_users.update(category_watchers)
            
        # Users with matching goals
        if hasattr(self, "_goal_service"):
            matching_goals = await self._goal_service.find_matching_goals(
                title=deal.title,
                category=deal.category,
                price=deal.price
            )
            for goal in matching_goals:
                interested_users.add(goal.user_id)
                
        return list(interested_users)
        
    except Exception as e:
        logger.error(f"Error finding interested users: {str(e)}")
        return []

def _serialize_flash_deal(self, deal) -> Dict[str, Any]:
    """Serialize a flash deal for API response.
    
    Args:
        deal: Deal object
        
    Returns:
        Serialized flash deal
    """
    return {
        "id": str(deal.id),
        "title": deal.title,
        "price": str(deal.price),
        "original_price": str(deal.original_price) if deal.original_price else None,
        "currency": deal.currency,
        "url": deal.url,
        "image_url": deal.image_url,
        "category": deal.category,
        "ai_score": getattr(deal, "ai_score", None),
        "expires_at": deal.flash_deal_expires_at.isoformat() if getattr(deal, "flash_deal_expires_at", None) else None,
        "discount_percentage": self._calculate_discount_percentage(deal.price, deal.original_price) if deal.original_price else None
    }

def _calculate_discount_percentage(self, price: Decimal, original_price: Decimal) -> int:
    """Calculate discount percentage.
    
    Args:
        price: Current price
        original_price: Original price
        
    Returns:
        Discount percentage as integer
    """
    if not original_price or original_price <= 0:
        return 0
        
    discount = ((original_price - price) / original_price) * 100
    return max(0, min(100, int(discount)))  # Ensure between 0-100%

async def _send_flash_deal_notifications(
    self,
    deal_id: UUID,
    user_ids: Optional[List[UUID]] = None
) -> Dict[str, Any]:
    """Send notifications about a flash deal to users.
    
    Args:
        deal_id: The ID of the flash deal
        user_ids: Optional list of specific users to notify, if None notifies all eligible users
        
    Returns:
        Dictionary with notification results
    """
    try:
        # Get deal details
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Cannot send flash deal notifications: deal {deal_id} not found")
            return {"status": "error", "reason": "Deal not found"}
            
        # Check if it's actually a flash deal
        if not getattr(deal, "is_flash_deal", False):
            logger.warning(f"Cannot send flash deal notifications: {deal_id} is not a flash deal")
            return {"status": "error", "reason": "Not a flash deal"}
            
        # Get users to notify
        if user_ids:
            # Use provided user IDs
            notify_users = user_ids
        else:
            # Find interested users
            notify_users = await self._find_interested_users(deal)
            
        if not notify_users:
            logger.info(f"No users to notify about flash deal {deal_id}")
            return {"status": "success", "notified_count": 0}
            
        # Create notification data
        notification_data = {
            "type": "flash_deal",
            "deal_id": str(deal_id),
            "title": deal.title,
            "price": str(deal.price),
            "original_price": str(deal.original_price) if deal.original_price else None,
            "discount_percentage": self._calculate_discount_percentage(deal.price, deal.original_price) if deal.original_price else None,
            "image_url": deal.image_url,
            "url": deal.url,
            "category": deal.category,
            "expires_at": deal.flash_deal_expires_at.isoformat() if hasattr(deal, "flash_deal_expires_at") and deal.flash_deal_expires_at else None,
            "is_limited_time": True,
            "ai_score": getattr(deal, "ai_score", None)
        }
        
        # Send notifications
        notify_count = 0
        for user_id in notify_users:
            # Check if this user already notified
            notified_key = f"notified:user:{user_id}:flash_deal:{deal_id}"
            already_notified = await self._redis_client.get(notified_key)
            
            if not already_notified:
                # Send notification and mark as notified
                await self._notification_service.send_notification(
                    user_id=user_id,
                    notification_type="flash_deal",
                    data=notification_data
                )
                
                # Mark as notified with 24-hour TTL to prevent duplicate notifications
                await self._redis_client.set(notified_key, "1", ex=86400)
                notify_count += 1
                
        logger.info(f"Sent flash deal notifications for {deal_id} to {notify_count} users")
        
        return {
            "status": "success",
            "deal_id": str(deal_id),
            "notified_count": notify_count,
            "total_eligible": len(notify_users)
        }
        
    except Exception as e:
        logger.error(f"Error sending flash deal notifications for {deal_id}: {str(e)}")
        return {"status": "error", "reason": str(e)} 