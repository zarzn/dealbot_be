"""Service for managing special promotions."""

from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.user import User
from core.models.token import Token, TokenTransaction
from core.models.market import Market
from core.models.deal import Deal
from core.exceptions.base_exceptions import NotFoundError, ValidationError
from core.utils.logger import get_logger

logger = get_logger(__name__)


class PromotionService:
    """Service for managing special promotions in the system."""
    
    def __init__(self, db: AsyncSession):
        """Initialize promotion service.
        
        Args:
            db: Database session
        """
        self.db = db
    
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
                        **metadata if metadata else {}
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
                        **metadata if metadata else {}
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
                        **metadata if metadata else {}
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
                        **metadata if metadata else {}
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