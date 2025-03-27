"""Service for managing special promotions."""

from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from uuid import UUID
from datetime import datetime, timedelta
import logging
from redis.asyncio import Redis
import json
from fastapi import Depends, HTTPException
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.user import User
from core.models.token import Token, TokenTransaction
from core.models.market import Market
from core.models.deal import Deal
from core.exceptions.base_exceptions import NotFoundError, ValidationError
from core.utils.logger import get_logger
from core.services.redis import get_redis_service
from core.database import get_async_db_context, get_async_db_session

logger = get_logger(__name__)


class PromotionService:
    """Service for managing special promotions in the system."""
    
    def __init__(self, db: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize promotion service.
        
        Args:
            db: Database session
            redis_service: Redis service for caching
        """
        self.db = db
        self._redis = redis_service
    
    async def create_token_promotion(
        self,
        title: str,
        description: str,
        token_amount: float,
        min_account_age_days: Optional[int] = None,
        max_account_age_days: Optional[int] = None,
        required_token_balance: Optional[float] = None,
        promotion_expiry: Optional[datetime] = None,
        max_recipients: Optional[int] = None,
        admin_id: UUID = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a special promotion that rewards users with tokens.
        
        Args:
            title: Promotion title
            description: Promotion description
            token_amount: Amount of tokens to reward
            min_account_age_days: Minimum account age in days to qualify
            max_account_age_days: Maximum account age in days to qualify
            required_token_balance: Minimum token balance to qualify
            promotion_expiry: When the promotion expires
            max_recipients: Maximum number of users to receive the promotion
            admin_id: ID of the admin creating the promotion
            metadata: Additional metadata for the promotion
            
        Returns:
            Promotion details with recipient count
            
        Raises:
            ValidationError: If invalid parameters provided
        """
        if token_amount <= 0:
            raise ValidationError("Token amount must be positive")
            
        if promotion_expiry and promotion_expiry < datetime.utcnow():
            raise ValidationError("Promotion expiry must be in the future")
            
        # Build query to find eligible users
        query = select(User).filter(User.status == "active")
        
        # Add account age filter if specified
        if min_account_age_days is not None or max_account_age_days is not None:
            now = datetime.utcnow()
            
            if min_account_age_days is not None:
                min_date = now - timedelta(days=min_account_age_days)
                query = query.filter(User.created_at <= min_date)
                
            if max_account_age_days is not None:
                max_date = now - timedelta(days=max_account_age_days)
                query = query.filter(User.created_at >= max_date)
        
        # Add token balance filter if specified
        if required_token_balance is not None:
            query = query.join(Token).filter(Token.balance >= required_token_balance)
            
        # Apply recipient limit
        if max_recipients is not None:
            query = query.limit(max_recipients)
            
        # Execute query to get eligible users
        result = await self.db.execute(query)
        eligible_users = result.scalars().all()
        
        if not eligible_users:
            logger.warning("No eligible users found for token promotion")
            return {
                "promotion_id": None,
                "title": title,
                "description": description,
                "token_amount": token_amount,
                "eligible_users": 0,
                "recipients": 0,
                "created_at": datetime.utcnow(),
                "status": "no_recipients"
            }
        
        # Send tokens and notifications to eligible users
        successful_recipients = 0
        
        # Import here to avoid circular imports
        from core.services.token import TokenService
        from core.notifications import TemplatedNotificationService
        
        token_service = TokenService(self.db)
        notification_service = TemplatedNotificationService(self.db)
        
        # Process each eligible user
        for user in eligible_users:
            try:
                # Record the token transaction
                transaction = await token_service.add_tokens(
                    user_id=user.id,
                    amount=token_amount,
                    reason="special_promotion",
                    admin_id=admin_id,
                    metadata={
                        "promotion_title": title,
                        "promotion_description": description,
                        **(metadata or {})
                    }
                )
                
                # Send notification
                await notification_service.send_notification(
                    template_id="special_promotion",
                    user_id=user.id,
                    template_params={
                        "promotion_title": title,
                        "promotion_description": description,
                        "token_amount": token_amount
                    },
                    metadata={
                        "promotion_type": "token_reward",
                        "token_amount": token_amount,
                        "transaction_id": str(transaction.id),
                        **(metadata or {})
                    }
                )
                
                successful_recipients += 1
                
            except Exception as e:
                logger.error(f"Failed to process promotion for user {user.id}: {str(e)}")
        
        # Return promotion summary
        return {
            "promotion_id": str(UUID.uuid4()),  # Generate a unique ID for reference
            "title": title,
            "description": description,
            "token_amount": token_amount,
            "eligible_users": len(eligible_users),
            "recipients": successful_recipients,
            "created_at": datetime.utcnow(),
            "status": "completed" if successful_recipients > 0 else "failed"
        }
    
    async def create_deal_promotion(
        self,
        market_id: UUID,
        discount_percentage: float,
        title: str,
        description: str,
        promotion_start: datetime,
        promotion_end: datetime,
        eligibility_criteria: Optional[Dict[str, Any]] = None,
        admin_id: UUID = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a special promotion for deals in a specific market.
        
        Args:
            market_id: Market ID for the promotion
            discount_percentage: Discount percentage (e.g., 10 for 10%)
            title: Promotion title
            description: Promotion description
            promotion_start: When the promotion starts
            promotion_end: When the promotion ends
            eligibility_criteria: Criteria for user eligibility
            admin_id: ID of the admin creating the promotion
            metadata: Additional metadata for the promotion
            
        Returns:
            Promotion details
            
        Raises:
            NotFoundError: If market not found
            ValidationError: If invalid parameters provided
        """
        # Validate inputs
        if discount_percentage <= 0 or discount_percentage > 100:
            raise ValidationError("Discount percentage must be between 0 and 100")
            
        if promotion_start >= promotion_end:
            raise ValidationError("Promotion end must be after start time")
            
        if promotion_start < datetime.utcnow():
            raise ValidationError("Promotion start must be in the future")
        
        # Check if market exists
        result = await self.db.execute(
            select(Market).filter(Market.id == market_id)
        )
        market = result.scalar_one_or_none()
        
        if not market:
            raise NotFoundError(f"Market with ID {market_id} not found")
        
        # Find users to notify about the promotion
        user_query = select(User).filter(User.status == "active")
        
        # Apply eligibility criteria if provided
        if eligibility_criteria:
            # Example: Filter by account age
            if "min_account_age_days" in eligibility_criteria:
                min_date = datetime.utcnow() - timedelta(days=eligibility_criteria["min_account_age_days"])
                user_query = user_query.filter(User.created_at <= min_date)
                
            # Example: Filter by market interaction
            if eligibility_criteria.get("has_interacted_with_market", False):
                user_query = user_query.join(Deal).filter(Deal.market_id == market_id)
        
        # Execute query to get eligible users
        result = await self.db.execute(user_query)
        eligible_users = result.scalars().all()
        
        # Send notifications to eligible users
        from core.notifications import TemplatedNotificationService
        notification_service = TemplatedNotificationService(self.db)
        
        notification_count = 0
        for user in eligible_users:
            try:
                await notification_service.send_notification(
                    template_id="special_promotion",
                    user_id=user.id,
                    template_params={
                        "promotion_title": title,
                        "promotion_description": description,
                        "market_name": market.name,
                        "discount_percentage": discount_percentage,
                        "promotion_start": promotion_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "promotion_end": promotion_end.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    metadata={
                        "promotion_type": "deal_discount",
                        "market_id": str(market_id),
                        "discount_percentage": discount_percentage,
                        "promotion_start": promotion_start.isoformat(),
                        "promotion_end": promotion_end.isoformat(),
                        **(metadata or {})
                    },
                    action_url=f"/markets/{market_id}"
                )
                notification_count += 1
            except Exception as e:
                logger.error(f"Failed to send promotion notification to user {user.id}: {str(e)}")
        
        # Return promotion summary
        return {
            "promotion_id": str(UUID.uuid4()),  # Generate a unique ID for reference
            "title": title,
            "description": description,
            "market_id": str(market_id),
            "market_name": market.name,
            "discount_percentage": discount_percentage,
            "promotion_start": promotion_start,
            "promotion_end": promotion_end,
            "eligible_users": len(eligible_users),
            "notified_users": notification_count,
            "created_at": datetime.utcnow(),
            "status": "scheduled" if notification_count > 0 else "failed"
        }
    
    async def create_flash_deal(
        self,
        deal_id: UUID,
        discount_percentage: float,
        title: str,
        description: str,
        duration_hours: int,
        admin_id: UUID = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a flash deal for a specific deal.
        
        Args:
            deal_id: Deal ID for the flash deal
            discount_percentage: Discount percentage (e.g., 10 for 10%)
            title: Flash deal title
            description: Flash deal description
            duration_hours: How long the flash deal lasts in hours
            admin_id: ID of the admin creating the flash deal
            metadata: Additional metadata for the flash deal
            
        Returns:
            Flash deal details
            
        Raises:
            NotFoundError: If deal not found
            ValidationError: If invalid parameters provided
        """
        # Validate inputs
        if discount_percentage <= 0 or discount_percentage > 100:
            raise ValidationError("Discount percentage must be between 0 and 100")
            
        if duration_hours <= 0:
            raise ValidationError("Duration must be positive")
        
        # Check if deal exists
        result = await self.db.execute(
            select(Deal).options(selectinload(Deal.market)).filter(Deal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        
        if not deal:
            raise NotFoundError(f"Deal with ID {deal_id} not found")
        
        # Calculate start and end times
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)
        
        # Find users who might be interested in this deal
        user_query = select(User).filter(
            or_(
                # Users who have interacted with this market before
                User.id.in_(
                    select(Deal.user_id).filter(
                        Deal.market_id == deal.market_id,
                        Deal.user_id.isnot(None)
                    )
                ),
                # Users who have viewed this deal
                User.id.in_(
                    select(Deal.viewed_by).filter(
                        Deal.id == deal_id
                    )
                )
            )
        )
        
        # Execute query to get eligible users
        result = await self.db.execute(user_query)
        eligible_users = result.scalars().all()
        
        # Send notifications to eligible users
        from core.notifications import TemplatedNotificationService
        notification_service = TemplatedNotificationService(self.db)
        
        notification_count = 0
        for user in eligible_users:
            try:
                await notification_service.send_notification(
                    template_id="flash_deal",
                    user_id=user.id,
                    template_params={
                        "deal_title": deal.title,
                        "deal_description": deal.description,
                        "market_name": deal.market.name,
                        "discount_percentage": discount_percentage,
                        "hours_remaining": duration_hours,
                        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "promotion_title": title,
                        "promotion_description": description
                    },
                    metadata={
                        "promotion_type": "flash_deal",
                        "deal_id": str(deal_id),
                        "market_id": str(deal.market_id),
                        "discount_percentage": discount_percentage,
                        "end_time": end_time.isoformat(),
                        **(metadata or {})
                    },
                    action_url=f"/deals/{deal_id}"
                )
                notification_count += 1
            except Exception as e:
                logger.error(f"Failed to send flash deal notification to user {user.id}: {str(e)}")
        
        # Return flash deal summary
        return {
            "flash_deal_id": str(UUID.uuid4()),  # Generate a unique ID for reference
            "title": title,
            "description": description,
            "deal_id": str(deal_id),
            "deal_title": deal.title,
            "market_id": str(deal.market_id),
            "market_name": deal.market.name,
            "discount_percentage": discount_percentage,
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": duration_hours,
            "eligible_users": len(eligible_users),
            "notified_users": notification_count,
            "created_at": datetime.utcnow(),
            "status": "active" if notification_count > 0 else "failed"
        }
    
    async def check_first_analysis_promotion(self, user_id: UUID) -> bool:
        """Check if user is eligible for the 'first analysis free' promotion.
        
        This method checks if a user is eligible for their first free deal analysis
        and marks the promotion as used if it was available.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            True if the user is eligible for the free promotion, False otherwise
        """
        # If Redis is not available, we'll use an in-memory flag as a fallback
        if not self._redis:
            try:
                # Try to get Redis service dynamically - maybe it's now available
                from core.services.redis import get_redis_service
                redis_service = await get_redis_service()
                if redis_service:
                    self._redis = redis_service
                    logger.info("Successfully reconnected to Redis for promotion check")
                else:
                    logger.warning("Redis still not available for promotion check, using fallback mechanism")
            except Exception as e:
                logger.warning(f"Error reconnecting to Redis: {str(e)}")
            
        # If Redis is still not available, use in-memory fallback
        if not self._redis:
            # Use a class-level static dictionary to track first-time users
            if not hasattr(self.__class__, '_first_analysis_users'):
                self.__class__._first_analysis_users = set()
                
            # Check if user has already used their free analysis in the current session
            user_id_str = str(user_id)
            if user_id_str in self.__class__._first_analysis_users:
                logger.info(f"User {user_id} has already used first analysis promotion (memory fallback)")
                return False
                
            # Mark as used in memory
            self.__class__._first_analysis_users.add(user_id_str)
            logger.info(f"User {user_id} is eligible for first analysis promotion (memory fallback)")
            return True
            
        # If Redis is available, use it as normal    
        try:
            promotion_key = f"first_analysis_promotion:{user_id}"
            
            # Check if the user has already used their free analysis
            promotion_used = await self._redis.exists(promotion_key)
            
            if not promotion_used:
                # User hasn't used their free analysis yet
                # Mark as used with a long expiry time (1 year)
                try:
                    await self._redis.setex(promotion_key, 60 * 60 * 24 * 365, "used")
                    logger.info(f"User {user_id} is eligible for first analysis promotion")
                    return True
                except Exception as redis_error:
                    # If we fail to mark the promotion as used, log and continue
                    # We'll still return True this time, but note the error
                    logger.error(f"Failed to mark promotion as used: {str(redis_error)}")
                    return True
                
            logger.info(f"User {user_id} has already used first analysis promotion")
            return False
            
        except Exception as e:
            # For any other Redis issues, log the error but don't fail the operation
            logger.error(f"Error checking first analysis promotion: {str(e)}")
            # In case of error, default to eligible (True) to provide better user experience
            # This is a non-critical feature so prefer user satisfaction over strict enforcement
            return True
    
    async def reset_first_analysis_promotion(self, user_id: UUID) -> bool:
        """Reset the first analysis promotion for a user.
        
        This method allows admins to reset a user's first analysis promotion,
        allowing them to get another free analysis.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            True if the promotion was reset, False otherwise
        """
        if not self._redis:
            logger.warning("Redis not available, cannot reset first analysis promotion")
            return False
            
        try:
            promotion_key = f"first_analysis_promotion:{user_id}"
            
            # Delete the key to reset the promotion
            result = await self._redis.delete(promotion_key)
            
            if result:
                logger.info(f"First analysis promotion reset for user {user_id}")
                return True
                
            logger.warning(f"Failed to reset first analysis promotion for user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error resetting first analysis promotion: {str(e)}")
            return False

async def get_promotion_service(
    db: AsyncSession = Depends(get_async_db_session),
    redis_service = Depends(get_redis_service)
) -> PromotionService:
    """Get promotion service dependency.
    
    Args:
        db: Database session
        redis_service: Redis service
        
    Returns:
        PromotionService instance
    """
    return PromotionService(db, redis_service) 