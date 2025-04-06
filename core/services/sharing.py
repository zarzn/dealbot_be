"""Sharing service.

This module provides functionality for sharing deals and search results with other users.
"""

import logging
import secrets
import string
import json
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, Depends

from core.models.shared_content import (
    SharedContent, ShareView, ShareableContentType, ShareVisibility,
    ShareContentRequest, ShareContentResponse, SharedContentDetail, SharedContentMetrics
)
from core.models.deal import Deal, DealResponse
from core.models.user import User
from core.exceptions.share_exceptions import ShareException
from core.database import get_async_db_context
from core.utils.json_utils import sanitize_for_json
from core.utils.logger import get_logger

logger = get_logger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects and other special types."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        # Handle pydantic HttpUrl
        elif hasattr(obj, '__str__') and (hasattr(obj, 'host') or hasattr(obj, 'scheme')):
            return str(obj)
        # Handle any other objects with __dict__
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)



def sanitize_for_json(data):
    """Recursively sanitize data to ensure it's JSON serializable."""
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime, UUID)):
        return str(data)
    elif hasattr(data, '__str__') and (hasattr(data, 'host') or hasattr(data, 'scheme')):
        return str(data)
    elif not isinstance(data, (str, int, float, bool, type(None))):
        return str(data)
    return data


def normalize_datetime(dt_value):
    """Normalize a datetime to be timezone-naive UTC.
    
    Args:
        dt_value: The datetime to normalize
        
    Returns:
        A timezone-naive datetime in UTC
    """
    if dt_value is None:
        return None
        
    # If datetime has timezone info, convert to UTC and remove timezone info
    if dt_value.tzinfo is not None:
        logger.debug(f"Converting timezone-aware datetime to naive: {dt_value}")
        return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Already naive, just return as is
    return dt_value


class SharingService:
    """Service for managing shared content."""

    def __init__(self, db: AsyncSession):
        """Initialize the sharing service."""
        self._db = db

    def _generate_share_id(self, length: int = 8) -> str:
        """Generate a unique, URL-friendly share ID.
        
        Args:
            length: Length of the ID to generate
            
        Returns:
            A unique share ID
        """
        # Use a mix of uppercase letters and numbers for readability
        # Exclude similar-looking characters (0, O, 1, I, etc.)
        alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def _ensure_unique_share_id(self, share_id: str) -> bool:
        """Check if a share ID is unique.
        
        Args:
            share_id: The share ID to check
            
        Returns:
            True if the ID is unique, False otherwise
        """
        result = await self._db.execute(
            select(SharedContent).where(SharedContent.share_id == share_id)
        )
        return result.scalar_one_or_none() is None

    async def create_shareable_content(
        self, 
        user_id: UUID,
        share_request: ShareContentRequest,
        base_url: str
    ) -> ShareContentResponse:
        """Create a new shareable content item.
        
        Args:
            user_id: ID of the user creating the share
            share_request: Details of the content to share
            base_url: Base URL for creating shareable links
            
        Returns:
            A response with the share details and link
            
        Raises:
            ShareException: If the content cannot be shared
        """
        # Generate a unique share ID
        share_id = self._generate_share_id()
        while not await self._ensure_unique_share_id(share_id):
            share_id = self._generate_share_id()
            
        # Set up expiration if requested - ensure timezone-naive datetime
        expires_at = None
        if share_request.expiration_days:
            # Create a timezone-naive datetime for consistency
            current_time = datetime.utcnow()
            expires_at = current_time + timedelta(days=share_request.expiration_days)
            logger.info(f"Setting expiration date: {expires_at}, type: {type(expires_at)}, has tzinfo: {expires_at.tzinfo is not None}")
            
        # Determine title if not provided
        title = share_request.title or "Shared Deal" if share_request.content_type == ShareableContentType.DEAL else "Shared Search Results"
            
        # Handle different content types
        if share_request.content_type == ShareableContentType.DEAL:
            if not share_request.content_id:
                raise ShareException("Content ID is required for sharing a deal")
                
            # Fetch the deal to snapshot its current state
            deal_query = select(Deal).where(Deal.id == share_request.content_id)
            result = await self._db.execute(deal_query)
            deal = result.scalar_one_or_none()
            
            if not deal:
                raise ShareException(f"Deal with ID {share_request.content_id} not found")
                
            # Convert to a response model to capture the presentation data
            try:
                # Ensure expires_at is normalized if present
                deal_expires_at = normalize_datetime(deal.expires_at) if deal.expires_at else None
                
                # Create a dictionary with the necessary fields for DealResponse
                deal_dict = {
                    # Copy properties from the deal
                    "id": deal.id,
                    "goal_id": deal.goal_id,
                    "market_id": deal.market_id,
                    "title": deal.title,
                    "description": deal.description,
                    "url": deal.url,
                    "price": deal.price,
                    "original_price": deal.original_price,
                    "currency": deal.currency,
                    "source": deal.source,
                    "image_url": deal.image_url,
                    "category": deal.category,
                    "seller_info": deal.seller_info,
                    "availability": deal.availability,
                    "found_at": deal.found_at,
                    "expires_at": deal_expires_at,
                    "status": deal.status,
                    "deal_metadata": deal.deal_metadata,
                    "price_metadata": deal.price_metadata,
                    "created_at": normalize_datetime(deal.created_at),
                    "updated_at": normalize_datetime(deal.updated_at),
                    
                    # Add required fields that are missing
                    "latest_score": deal.score,  # Use the score from Deal as latest_score
                    "price_history": []  # Empty list as default for price_history
                }
                
                # Validate the model with our prepared dictionary
                deal_data = DealResponse.model_validate(deal_dict)
            except Exception as e:
                logger.error(f"Error creating deal response: {str(e)}")
                raise ShareException(f"Failed to create shareable content: {str(e)}")
            
            # Create content data including the deal snapshot
            try:
                # First convert to dictionary
                deal_dict = deal_data.model_dump()
                # Ensure all values are JSON serializable
                content_data = {
                    "deal": deal_dict,
                    "personal_notes": share_request.personal_notes if share_request.include_personal_notes else None
                }
            except Exception as e:
                logger.error(f"Error creating content data: {str(e)}")
                raise ShareException(f"Failed to create shareable content: {str(e)}")
            
            # Use deal title if no custom title provided
            if not share_request.title:
                title = f"Check out this deal: {deal.title}"
                
        elif share_request.content_type == ShareableContentType.SEARCH_RESULTS:
            if not share_request.search_params:
                raise ShareException("Search parameters are required for sharing search results")
                
            # Snapshot the search parameters and results
            try:
                content_data = {
                    "search_params": share_request.search_params,
                    "personal_notes": share_request.personal_notes if share_request.include_personal_notes else None
                }
            except Exception as e:
                logger.error(f"Error preparing search params: {str(e)}")
                raise ShareException(f"Failed to prepare search parameters: {str(e)}")
            
            # Use search query in title if no custom title provided
            if not share_request.title and share_request.search_params.get("query"):
                title = f"Search results for: {share_request.search_params['query']}"
        else:
            raise ShareException(f"Unsupported content type: {share_request.content_type}")
            
        # Create the shared content record
        try:
            # Serialize content_data with the custom encoder that handles datetime and HttpUrl objects
            try:
                serialized_content = json.dumps(content_data, cls=DateTimeEncoder)
                serialized_content_data = json.loads(serialized_content)
            except Exception as e:
                logger.error(f"Error serializing content data: {str(e)}")
                # Fallback - try stringifying problematic values
                sanitized_data = sanitize_for_json(content_data)
                serialized_content = json.dumps(sanitized_data)
                serialized_content_data = json.loads(serialized_content)
            
            new_share = SharedContent(
                user_id=user_id,
                share_id=share_id,
                title=title,
                description=share_request.description,
                content_type=share_request.content_type.value,
                content_id=share_request.content_id,
                content_data=serialized_content_data,
                visibility=share_request.visibility.value,
                expires_at=expires_at,
                is_active=True,
                view_count=0
            )
            
            self._db.add(new_share)
            await self._db.flush()
        except Exception as e:
            logger.error(f"Error creating shareable content: {str(e)}")
            raise ShareException(f"Failed to create shareable content: {str(e)}")
        
        # Construct the shareable link with the frontend path structure instead of API path
        # Using frontend route instead of API endpoint for better user experience
        # Ensure base_url doesn't have trailing slash to avoid double slashes
        base_url = base_url.rstrip('/')
        shareable_link = f"{base_url}/shared-deal/{share_id}"
        
        # Log the generated link for debugging
        logger.info(f"Generated shareable link: {shareable_link} for content ID: {share_request.content_id}")
        
        # Use current_time for created_at to ensure timezone consistency
        current_time = datetime.utcnow()
        
        return ShareContentResponse(
            share_id=share_id,
            title=title,
            description=share_request.description,
            content_type=share_request.content_type,
            shareable_link=shareable_link,
            expiration_date=expires_at,
            created_at=current_time
        )

    async def get_shared_content(
        self, 
        share_id: str, 
        viewer_id: Optional[UUID] = None, 
        viewer_ip: Optional[str] = None,
        viewer_device: Optional[str] = None,
        referrer: Optional[str] = None
    ) -> SharedContentDetail:
        """Get shared content by share ID.
        
        Args:
            share_id: The unique share ID
            viewer_id: ID of the authenticated user viewing the content (if any)
            viewer_ip: IP address of the viewer
            viewer_device: Device information of the viewer
            referrer: Referring URL
            
        Returns:
            The shared content details
            
        Raises:
            ShareException: If the content is not found or has expired
        """
        # Query the shared content
        query = (
            select(SharedContent)
            .options(joinedload(SharedContent.user))
            .where(SharedContent.share_id == share_id)
        )
        result = await self._db.execute(query)
        shared_content = result.scalar_one_or_none()
        
        if not shared_content:
            raise ShareException(f"Shared content with ID {share_id} not found")
            
        if not shared_content.is_active:
            raise ShareException("This shared content has been deactivated")
        
        # Fix timezone comparison - normalize all datetimes
        current_time = datetime.utcnow()
        expires_at = normalize_datetime(shared_content.expires_at)
        
        if expires_at is not None:
            # Log the types for debugging
            logger.info(f"Comparing datetimes - Current: {current_time} ({type(current_time)}), Expires: {expires_at} ({type(expires_at)})")
            logger.info(f"Timezone info - Current: {current_time.tzinfo}, Expires: {expires_at.tzinfo}")
            
            # Compare normalized datetimes
            if expires_at < current_time:
                logger.info(f"Share expired: expires_at={expires_at}, current={current_time}")
                raise ShareException("This shared link has expired")
            
        # For private content, require authentication
        if shared_content.visibility == ShareVisibility.PRIVATE.value and not viewer_id:
            raise ShareException("This content requires authentication to view")
            
        # Record the view
        await self._record_view(
            shared_content.id,
            viewer_id,
            viewer_ip,
            viewer_device,
            referrer
        )
        
        # Increment view count
        shared_content.view_count += 1
        await self._db.flush()
        
        # Create the response
        creator_name = shared_content.user.name if shared_content.user else "Anonymous"
        
        # Normalize datetime values for response
        created_at = normalize_datetime(shared_content.created_at)
        
        response = SharedContentDetail(
            share_id=shared_content.share_id,
            title=shared_content.title,
            description=shared_content.description,
            content_type=ShareableContentType(shared_content.content_type),
            content=shared_content.content_data,
            created_by=creator_name,
            created_at=created_at,
            expires_at=expires_at,
            view_count=shared_content.view_count,
            personal_notes=shared_content.content_data.get("personal_notes")
        )
        
        return response
        
    async def _record_view(
        self,
        shared_content_id: UUID,
        viewer_id: Optional[UUID],
        viewer_ip: Optional[str],
        viewer_device: Optional[str],
        referrer: Optional[str]
    ) -> None:
        """Record a view of shared content.
        
        Args:
            shared_content_id: ID of the shared content
            viewer_id: ID of the authenticated user viewing the content (if any)
            viewer_ip: IP address of the viewer
            viewer_device: Device information of the viewer
            referrer: Referring URL
        """
        try:
            view = ShareView(
                shared_content_id=shared_content_id,
                viewer_id=viewer_id,
                viewer_ip=viewer_ip,
                viewer_device=viewer_device,
                viewed_at=datetime.utcnow(),
                referrer=referrer
            )
            
            self._db.add(view)
            await self._db.flush()
        except Exception as e:
            logger.error(f"Error recording view: {str(e)}")
            # Continue even if view recording fails
            # This is non-critical functionality
        
    async def get_user_shared_content(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 20,
        content_type: Optional[ShareableContentType] = None,
        base_url: str = None
    ) -> List[ShareContentResponse]:
        """Get all shared content created by a user.
        
        Args:
            user_id: ID of the user
            offset: Number of items to skip
            limit: Maximum number of items to return
            content_type: Filter by content type
            base_url: Base URL for creating shareable links
            
        Returns:
            A list of shared content items
        """
        query = (
            select(SharedContent)
            .where(SharedContent.user_id == user_id)
            .order_by(SharedContent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        if content_type:
            query = query.where(SharedContent.content_type == content_type.value)
            
        result = await self._db.execute(query)
        shared_contents = result.scalars().all()
        
        # Use current time for consistency
        current_time = datetime.utcnow()
        
        # Create shareable link using the frontend route pattern
        # If base_url is not provided, use a relative URL that frontend will resolve
        link_base = base_url if base_url else ""
        
        return [
            ShareContentResponse(
                share_id=item.share_id,
                title=item.title,
                description=item.description,
                content_type=ShareableContentType(item.content_type),
                shareable_link=f"{link_base}/shared-deal/{item.share_id}",  # Use the frontend route pattern
                expiration_date=normalize_datetime(item.expires_at),
                created_at=normalize_datetime(item.created_at) or current_time
            )
            for item in shared_contents
        ]
        
    async def get_metrics(self, share_id: str, user_id: UUID) -> SharedContentMetrics:
        """Get engagement metrics for a shared content item.
        
        Args:
            share_id: The unique share ID
            user_id: ID of the user requesting metrics (must be the creator)
            
        Returns:
            Metrics for the shared content
            
        Raises:
            ShareException: If the content is not found or user is not authorized
        """
        # Get the shared content
        query = select(SharedContent).where(SharedContent.share_id == share_id)
        result = await self._db.execute(query)
        shared_content = result.scalar_one_or_none()
        
        if not shared_content:
            raise ShareException(f"Shared content with ID {share_id} not found")
            
        # Verify ownership
        if shared_content.user_id != user_id:
            raise ShareException("You are not authorized to view metrics for this content")
            
        # Get view data
        views_query = select(ShareView).where(ShareView.shared_content_id == shared_content.id)
        views_result = await self._db.execute(views_query)
        views = views_result.scalars().all()
        
        # Count unique viewers
        unique_viewers = len(set(view.viewer_id for view in views if view.viewer_id))
        
        # Count referring sites
        referring_sites = {}
        for view in views:
            if view.referrer:
                # Extract domain from referrer
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(view.referrer).netloc
                    referring_sites[domain] = referring_sites.get(domain, 0) + 1
                except:
                    # If parsing fails, use the full referrer
                    referring_sites[view.referrer] = referring_sites.get(view.referrer, 0) + 1
        
        # Count viewer devices
        viewer_devices = {}
        for view in views:
            if view.viewer_device:
                viewer_devices[view.viewer_device] = viewer_devices.get(view.viewer_device, 0) + 1
        
        # Get last viewed time - normalize datetimes
        if views:
            view_datetimes = [normalize_datetime(view.viewed_at) for view in views if view.viewed_at]
            last_viewed = max(view_datetimes) if view_datetimes else None
        else:
            last_viewed = None
        
        # Ensure serializable data
        try:
            # Convert referring_sites and viewer_devices to JSON and back to ensure they're serializable
            referring_sites = json.loads(json.dumps(referring_sites, cls=DateTimeEncoder))
            viewer_devices = json.loads(json.dumps(viewer_devices, cls=DateTimeEncoder))
            
            # Normalize created_at
            created_at = normalize_datetime(shared_content.created_at)
            
            return SharedContentMetrics(
                share_id=share_id,
                view_count=shared_content.view_count,
                unique_viewers=unique_viewers,
                referring_sites=referring_sites,
                viewer_devices=viewer_devices,
                created_at=created_at,
                last_viewed=last_viewed
            )
        except Exception as e:
            logger.error(f"Error serializing metrics data: {str(e)}")
            # Return simplified metrics if serialization fails
            return SharedContentMetrics(
                share_id=share_id,
                view_count=shared_content.view_count,
                unique_viewers=unique_viewers,
                referring_sites={},
                viewer_devices={},
                created_at=normalize_datetime(shared_content.created_at),
                last_viewed=None
            )
        
    async def deactivate_share(self, share_id: str, user_id: UUID) -> bool:
        """Deactivate a shared content item.
        
        Args:
            share_id: The unique share ID
            user_id: ID of the user requesting deactivation (must be the creator)
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ShareException: If the content is not found or user is not authorized
        """
        # Get the shared content
        query = select(SharedContent).where(SharedContent.share_id == share_id)
        result = await self._db.execute(query)
        shared_content = result.scalar_one_or_none()
        
        if not shared_content:
            raise ShareException(f"Shared content with ID {share_id} not found")
            
        # Verify ownership
        if shared_content.user_id != user_id:
            raise ShareException("You are not authorized to deactivate this content")
            
        # Deactivate the content
        shared_content.is_active = False
        await self._db.flush()
        
        return True

    async def delete_expired_shares(self) -> Dict[str, Any]:
        """
        Delete all expired shares from the database.
        
        This method identifies all shares that have passed their expiration date
        and removes them from the database to keep it clean and efficient.
        
        Returns:
            Dict containing the number of removed shares and operation status
        """
        async with async_session_factory() as session:
            try:
                current_time = datetime.utcnow()
                # Find expired shares
                query = (
                    select(models.ShareableContent)
                    .where(
                        and_(
                            models.ShareableContent.expires_at.isnot(None),
                            models.ShareableContent.expires_at < current_time
                        )
                    )
                )
                
                result = await session.execute(query)
                expired_shares = result.scalars().all()
                expired_share_ids = [share.id for share in expired_shares]
                
                # Log the number of shares found for cleanup
                logger.info(f"Found {len(expired_share_ids)} expired shares to clean up")
                
                if expired_share_ids:
                    # Delete the shares
                    delete_query = (
                        delete(models.ShareableContent)
                        .where(models.ShareableContent.id.in_(expired_share_ids))
                    )
                    delete_result = await session.execute(delete_query)
                    await session.commit()
                    
                    # Log successful deletion
                    removed_count = delete_result.rowcount
                    logger.info(f"Successfully deleted {removed_count} expired shares")
                    return {"status": "success", "removed_count": removed_count}
                else:
                    # No expired shares found
                    logger.info("No expired shares found to clean up")
                    return {"status": "success", "removed_count": 0}
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting expired shares: {str(e)}")
                raise ServiceException(f"Failed to delete expired shares: {str(e)}")


async def get_sharing_service(db: AsyncSession = Depends(get_async_db_context)) -> SharingService:
    """Get an instance of the sharing service.
    
    This is a FastAPI dependency that provides an instance of the SharingService.
    
    Args:
        db: The database session
        
    Returns:
        An instance of SharingService
    """
    return SharingService(db) 