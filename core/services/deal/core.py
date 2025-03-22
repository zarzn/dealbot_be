"""Core CRUD operations for the DealService.

This module contains the core CRUD operations for the DealService, including:
- create_deal: Create a new deal
- get_deal: Get a deal by ID
- process_deals_batch: Process multiple deals in batch
- update_deal: Update an existing deal
- delete_deal: Delete a deal
- list_deals: List deals with optional filtering
- get_deals: Get deals for a user with optional filtering
- get_deal_by_id: Get a specific deal by ID
- get_recent_deals: Get the most recent deals
"""

import asyncio
import logging
import json
import functools
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
from uuid import UUID
from decimal import Decimal
from fastapi import BackgroundTasks
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User
from core.models.deal import Deal, DealStatus, PriceHistory
from core.models.goal import Goal
from core.models.market import Market
from core.exceptions import (
    DealError,
    DealNotFoundError,
    InvalidDealDataError,
    RateLimitExceededError,
    DatabaseError,
    ExternalServiceError,
    ValidationError
)
from core.utils.redis import get_redis_client
from core.config import settings

# Import from local modules
from .utils import log_exceptions

logger = logging.getLogger(__name__)

# Configuration constants
API_CALLS_PER_MINUTE = 60
DEAL_ANALYSIS_RETRIES = 3
MAX_BATCH_SIZE = 100


@sleep_and_retry
@limits(calls=API_CALLS_PER_MINUTE, period=60)
async def create_deal(
    self,
    user_id: UUID,
    goal_id: UUID,
    market_id: UUID,
    title: str,
    description: Optional[str] = None,
    price: Decimal = Decimal('0.01'),
    original_price: Optional[Decimal] = None,
    currency: str = 'USD',
    source: str = 'manual',
    url: Optional[str] = None,
    image_url: Optional[str] = None,
    category: Optional[str] = None,
    seller_info: Optional[Dict[str, Any]] = None,
    deal_metadata: Optional[Dict[str, Any]] = None,
    price_metadata: Optional[Dict[str, Any]] = None,
    expires_at: Optional[datetime] = None,
    status: str = DealStatus.ACTIVE.value
) -> Deal:
    """Create a new deal with score calculation
    
    Args:
        user_id: User who created the deal
        goal_id: Goal ID associated with the deal
        market_id: Market ID associated with the deal
        title: Title of the deal
        description: Description of the deal
        price: Current price
        original_price: Original price before discount
        currency: Currency code (3-letter ISO)
        source: Source of the deal
        url: URL to the deal
        image_url: URL to the product image
        category: Product category
        seller_info: Information about the seller
        deal_metadata: Additional metadata about the deal
        price_metadata: Additional metadata about the price
        expires_at: Expiration date of the deal
        status: Deal status
        
    Returns:
        Deal: Created deal object
        
    Raises:
        RateLimitExceededError: If rate limit is exceeded
        AIServiceError: If AI service fails
        ExternalServiceError: If external service fails
    """
    try:
        # Check for existing deal with same URL and goal_id to prevent unique constraint violation
        existing_deal = await self._repository.get_by_url_and_goal(url, goal_id)
        if existing_deal:
            logger.info(f"Deal with URL {url} and goal_id {goal_id} already exists")
            return existing_deal
            
        # Create deal object
        deal = Deal(
            user_id=user_id,
            goal_id=goal_id,
            market_id=market_id,
            title=title,
            description=description,
            price=price,
            original_price=original_price,
            currency=currency,
            source=source,
            url=url,
            image_url=image_url,
            category=category,
            seller_info=seller_info,
            deal_metadata=deal_metadata if deal_metadata else {},
            price_metadata=price_metadata if price_metadata else {},
            expires_at=expires_at,
            status=status
        )
        
        # Calculate score using AI
        score = await self._calculate_deal_score(deal)
        
        # Add score to deal data - but don't include it in the creation dictionary
        # SQLAlchemy models don't have dict() method, so create a new dictionary
        deal_data_dict = {
            'user_id': user_id,
            'goal_id': goal_id,
            'market_id': market_id,
            'title': title,
            'description': description,
            'price': price,
            'original_price': original_price,
            'currency': currency,
            'source': source,
            'url': url,
            'image_url': image_url,
            'category': category,
            'seller_info': seller_info,
            'deal_metadata': deal_metadata,
            'price_metadata': price_metadata,
            'expires_at': expires_at,
            'status': status
            # score is handled separately
        }
        
        # Create deal in database - must await the coroutine
        deal = await self._repository.create(deal_data_dict)
        
        # Store the score separately if needed
        # This could involve updating the deal or storing in a separate scores table
        
        # Cache deal data with separate TTLs
        await self._cache_deal(deal)
        
        logger.info(f"Successfully created deal {deal.id} with score {score}")
        return deal
        
    except RateLimitExceededError:
        logger.warning("Rate limit exceeded while creating deal")
        raise
    except AIServiceError as e:
        logger.error(f"AI service error while creating deal: {str(e)}")
        raise
    except ExternalServiceError as e:
        logger.error(f"External service error while creating deal: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while creating deal: {str(e)}")
        raise ExternalServiceError(service="deal_service", operation="create_deal", message=f"Failed to create deal: {str(e)}")


@retry(stop=stop_after_attempt(DEAL_ANALYSIS_RETRIES), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_deal(self, deal_id: str, user_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Get deal by ID with cache fallback and retry mechanism"""
    try:
        # Try to get from cache first
        cached_deal = await self._get_cached_deal(deal_id)
        if cached_deal:
            # Convert to response before returning
            return self._convert_to_response(cached_deal, user_id)
            
        # Fallback to database
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.error(f"Deal with ID {deal_id} not found")
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Cache the deal
        await self._cache_deal(deal)
        
        # Convert to response before returning
        return self._convert_to_response(deal, user_id)
    except DealNotFoundError:
        # Re-raise DealNotFoundError to be caught by the retry mechanism
        raise
    except Exception as e:
        logger.error(f"Failed to get deal: {str(e)}")
        raise


async def process_deals_batch(self, deals: List[Any]) -> List[Deal]:
    """Process multiple deals in batch with background tasks and rate limiting
    
    Args:
        deals: List of DealCreate objects to process
        
    Returns:
        List[Deal]: List of successfully processed deals
        
    Raises:
        RateLimitExceededError: If API rate limit is exceeded
        ExternalServiceError: If external service fails
    """
    processed_deals = []
    batch_size = min(len(deals), MAX_BATCH_SIZE)
    
    try:
        for i, deal_data in enumerate(deals[:batch_size]):
            try:
                # Process each deal in background with rate limiting
                self.add_background_task(
                    self._process_single_deal_with_retry, 
                    deal_data
                )
                processed_deals.append(deal_data)
                
                # Rate limit control
                if (i + 1) % 10 == 0:
                    await asyncio.sleep(1)
                    
            except RateLimitExceededError:
                logger.warning("Rate limit reached, pausing batch processing")
                await asyncio.sleep(60)  # Wait 1 minute before continuing
                continue
            except Exception as e:
                logger.error(f"Failed to process deal: {str(e)}")
                continue
                
        logger.info(f"Successfully processed {len(processed_deals)} deals in batch")
        return processed_deals
        
    except Exception as e:
        logger.error(f"Failed to process batch of deals: {str(e)}")
        raise ExternalServiceError(
            service="deal_service", 
            operation="process_deals_batch", 
            message=f"Failed to process batch of deals: {str(e)}"
        )


@retry(stop=stop_after_attempt(DEAL_ANALYSIS_RETRIES),
       wait=wait_exponential(multiplier=1, min=4, max=10))
async def _process_single_deal_with_retry(self, deal_data: Any) -> Deal:
    """Process single deal with retry mechanism"""
    return await self._process_single_deal(deal_data)


async def _process_single_deal(self, deal_data: Any) -> Deal:
    """Process a single deal with AI scoring, validation, and analysis"""
    try:
        # Extract required fields from deal_data
        user_id = getattr(deal_data, 'user_id', None)
        goal_id = getattr(deal_data, 'goal_id', None)
        market_id = getattr(deal_data, 'market_id', None)
        title = getattr(deal_data, 'title', None) or getattr(deal_data, 'product_name', None)
        
        # Apply AI scoring and analysis
        score = await self._calculate_deal_score(deal_data)
        analysis = await self._analyze_deal(deal_data)
        
        # Create deal with score and analysis
        deal_dict = deal_data.dict() if hasattr(deal_data, 'dict') else deal_data
        deal_dict.update({
            'score': score,
            'analysis': analysis
        })
        
        deal = await self.create_deal(**deal_dict)
        return deal
    except Exception as e:
        logger.error(f"Failed to process single deal: {str(e)}")
        raise ExternalServiceError(
            service="deal_service", 
            operation="process_deal", 
            message=f"Failed to process single deal: {str(e)}"
        )


@log_exceptions
@sleep_and_retry
@limits(calls=API_CALLS_PER_MINUTE, period=60)
async def update_deal(self, deal_id: UUID, **deal_data) -> Deal:
    """
    Update an existing deal.
    
    Args:
        deal_id: The ID of the deal to update
        **deal_data: The deal attributes to update
        
    Returns:
        The updated deal
        
    Raises:
        DealNotFoundError: If the deal is not found
        RateLimitExceededError: If the rate limit is exceeded
        DatabaseError: If there is a database error
    """
    try:
        # Get the deal first to check if it exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Check if status is being updated
        original_status = deal.status
        new_status = deal_data.get('status')
        
        # Update the deal
        updated_deal = await self._repository.update(deal_id, deal_data)
        
        # Update cache if Redis is available
        if self._redis:
            await self._cache_deal(updated_deal)
            
        # Send notification if status changed
        if new_status and original_status != new_status:
            try:
                # Import here to avoid circular imports
                from core.notifications import TemplatedNotificationService
                
                # Get related goals - we'll notify users who have this deal in their goals
                from core.models.goal import Goal
                
                # Create notification service
                notification_service = TemplatedNotificationService(self.session)
                
                # Get the user who owns the deal
                if updated_deal.user_id:
                    # Format the status nicely for display
                    status_display = new_status.replace("_", " ").title()
                    
                    # Send notification about status change
                    await notification_service.send_notification(
                        template_id="deal_status_update",
                        user_id=updated_deal.user_id,
                        template_params={
                            "deal_title": updated_deal.title,
                            "status": status_display
                        },
                        metadata={
                            "deal_id": str(deal_id),
                            "previous_status": original_status,
                            "new_status": new_status
                        },
                        deal_id=deal_id
                    )
                
                # If there's a goal associated with this deal, also notify goal owner
                if updated_deal.goal_id:
                    stmt = select(Goal).where(Goal.id == updated_deal.goal_id)
                    result = await self.session.execute(stmt)
                    goal = result.scalar_one_or_none()
                    
                    if goal and goal.user_id and goal.user_id != updated_deal.user_id:
                        # Format the status nicely
                        status_display = new_status.replace("_", " ").title()
                        
                        # Send notification to goal owner
                        await notification_service.send_notification(
                            template_id="deal_status_update",
                            user_id=goal.user_id,
                            template_params={
                                "deal_title": updated_deal.title,
                                "status": status_display
                            },
                            metadata={
                                "deal_id": str(deal_id),
                                "goal_id": str(goal.id),
                                "previous_status": original_status,
                                "new_status": new_status
                            },
                            goal_id=goal.id,
                            deal_id=deal_id
                        )
            except Exception as notification_error:
                # Log but don't fail the update
                logger.error(f"Failed to send deal status notification: {str(notification_error)}")
            
        return updated_deal
    except DealNotFoundError:
        raise
    except RateLimitExceededError as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to update deal {deal_id}: {str(e)}")
        raise DatabaseError(f"Failed to update deal: {str(e)}", "update_deal") from e


@log_exceptions
@sleep_and_retry
@limits(calls=API_CALLS_PER_MINUTE, period=60)
async def delete_deal(self, deal_id: UUID) -> None:
    """
    Delete a deal.
    
    Args:
        deal_id: The ID of the deal to delete
        
    Raises:
        DealNotFoundError: If the deal is not found
        RateLimitExceededError: If the rate limit is exceeded
        DatabaseError: If there is a database error
    """
    try:
        # Get the deal first to check if it exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Delete the deal
        await self._repository.delete(deal_id)
        
        # Clear cache if Redis is available
        if self._redis:
            await self._redis.delete(f"deal:{deal_id}:full")
            await self._redis.delete(f"deal:{deal_id}:basic")
            await self._redis.delete(f"deal:{deal_id}:price_history")
            
    except DealNotFoundError:
        raise
    except RateLimitExceededError as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to delete deal {deal_id}: {str(e)}")
        raise DatabaseError(f"Failed to delete deal: {str(e)}", "delete_deal") from e


async def list_deals(
    self,
    user_id: Optional[UUID] = None,
    goal_id: Optional[UUID] = None,
    market_id: Optional[UUID] = None,
    status: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Deal]:
    """List deals with optional filtering.
    
    Args:
        user_id: Filter by user ID
        goal_id: Filter by goal ID
        market_id: Filter by market ID
        status: Filter by deal status
        min_price: Filter by minimum price
        max_price: Filter by maximum price
        limit: Maximum number of deals to return
        offset: Number of deals to skip
        
    Returns:
        List of deals matching the filters
    """
    try:
        # Build base query
        query = select(Deal)
        
        # Apply filters
        if user_id:
            query = query.filter(Deal.user_id == user_id)
        if goal_id:
            query = query.filter(Deal.goal_id == goal_id)
        if market_id:
            query = query.filter(Deal.market_id == market_id)
        if status:
            query = query.filter(Deal.status == status)
        if min_price is not None:
            query = query.filter(Deal.price >= min_price)
        if max_price is not None:
            query = query.filter(Deal.price <= max_price)
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await self._repository.db.execute(query)
        deals = result.scalars().unique().all()
        
        return list(deals)
    except Exception as e:
        logger.error(f"Failed to list deals: {str(e)}")
        raise DealError(f"Failed to list deals: {str(e)}")


async def get_deals(
    self,
    user_id: UUID,
    filters: Optional[Any] = None,
    page: int = 1,
    page_size: int = 20
) -> List[Dict[str, Any]]:
    """
    Get deals for a user with optional filtering.
    
    Args:
        user_id: The ID of the user
        filters: Optional filters for the deals
        page: Page number (starting from 1)
        page_size: Number of items per page
        
    Returns:
        List of deals
        
    Raises:
        DatabaseError: If there is a database error
    """
    try:
        # Calculate offset from page and page_size
        offset = (page - 1) * page_size
        
        # Get deals from repository
        deals = await self._repository.get_by_user(
            user_id=user_id,
            limit=page_size,
            offset=offset,
            filters=filters
        )
        
        # Convert to dictionaries
        return [deal.to_dict() if hasattr(deal, 'to_dict') else deal for deal in deals]
        
    except Exception as e:
        logger.error(f"Failed to get deals for user {user_id}: {str(e)}")
        raise DatabaseError(f"Failed to get deals: {str(e)}", "get_deals") from e


async def get_deal_by_id(
    self,
    deal_id: UUID,
    user_id: Optional[UUID] = None
) -> Optional[Dict[str, Any]]:
    """
    Get a specific deal by ID
    
    Args:
        deal_id: The ID of the deal to retrieve
        user_id: Optional user ID for access control or tracking
        
    Returns:
        Deal response or None if not found
    """
    from sqlalchemy.orm import joinedload
    
    query = select(Deal).options(
        joinedload(Deal.price_points),
        joinedload(Deal.tracked_by_users)
    ).filter(Deal.id == deal_id)

    deal = await self._repository.db.execute(query)
    deal = deal.scalar_one_or_none()

    if not deal:
        return None

    return self._convert_to_response(deal, user_id)


@log_exceptions
async def get_recent_deals(
    self,
    user_id: Optional[UUID] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Get the most recent deals.
    
    Args:
        user_id: Optional user ID (not required for public access)
        limit: Maximum number of deals to return
        
    Returns:
        List of recent deals in response format
        
    Raises:
        DatabaseError: If there is a database error
    """
    try:
        # Query for the most recent deals
        query = select(Deal).order_by(Deal.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        # Convert deals to response format
        response_deals = []
        for deal in deals:
            response_deals.append(self._convert_to_response(deal, user_id))
            
        return response_deals
    except Exception as e:
        logger.error(f"Failed to get recent deals: {str(e)}")
        raise DatabaseError(f"Failed to get recent deals: {str(e)}", "get_recent_deals") from e 