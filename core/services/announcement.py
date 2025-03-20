"""Announcement service for the system."""

from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from core.models.announcement import (
    Announcement,
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
    AnnouncementType,
    AnnouncementStatus
)
from core.models.user import User
from core.exceptions.base_exceptions import NotFoundError, ValidationError
from core.utils.logger import get_logger

logger = get_logger(__name__)

class AnnouncementService:
    """Service for managing system announcements."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the announcement service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def create_announcement(
        self,
        data: AnnouncementCreate,
        user_id: UUID
    ) -> AnnouncementResponse:
        """Create a new announcement.
        
        Args:
            data: Announcement data
            user_id: ID of the user creating the announcement
            
        Returns:
            Created announcement
            
        Raises:
            ValidationError: If the data is invalid
        """
        try:
            # Create the announcement
            announcement = Announcement(
                title=data.title,
                content=data.content,
                type=data.type.value,
                status=data.status.value,
                is_important=data.is_important,
                publish_at=data.publish_at,
                expire_at=data.expire_at,
                target_user_groups=data.target_user_groups,
                announcement_metadata=data.announcement_metadata,
                action_url=data.action_url,
                action_text=data.action_text,
                created_by=user_id
            )
            
            # Add to the database
            self.db.add(announcement)
            await self.db.commit()
            await self.db.refresh(announcement)
            
            # If the announcement is published, send notifications
            if announcement.status == AnnouncementStatus.PUBLISHED.value:
                await self._send_announcement_notifications(announcement)
                
            return AnnouncementResponse.model_validate(announcement)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create announcement: {str(e)}")
            raise ValidationError(f"Failed to create announcement: {str(e)}")
    
    async def get_announcement(self, announcement_id: UUID) -> AnnouncementResponse:
        """Get an announcement by ID.
        
        Args:
            announcement_id: ID of the announcement
            
        Returns:
            Announcement
            
        Raises:
            NotFoundError: If announcement not found
        """
        announcement = await self._get_announcement_by_id(announcement_id)
        return AnnouncementResponse.model_validate(announcement)
    
    async def get_announcements(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[AnnouncementStatus] = None,
        type: Optional[AnnouncementType] = None
    ) -> List[AnnouncementResponse]:
        """Get all announcements.
        
        Args:
            skip: Number of announcements to skip
            limit: Maximum number of announcements to return
            status: Filter by status
            type: Filter by type
            
        Returns:
            List of announcements
        """
        # Build the query
        query = select(Announcement).options(selectinload(Announcement.creator))
        
        # Apply filters
        if status:
            query = query.filter(Announcement.status == status.value)
        if type:
            query = query.filter(Announcement.type == type.value)
            
        # Order by creation date (newest first)
        query = query.order_by(desc(Announcement.created_at))
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute the query
        result = await self.db.execute(query)
        announcements = result.scalars().all()
        
        return [AnnouncementResponse.model_validate(a) for a in announcements]
    
    async def update_announcement(
        self,
        announcement_id: UUID,
        data: AnnouncementUpdate,
        user_id: UUID
    ) -> AnnouncementResponse:
        """Update an announcement.
        
        Args:
            announcement_id: ID of the announcement
            data: Updated announcement data
            user_id: ID of the user updating the announcement
            
        Returns:
            Updated announcement
            
        Raises:
            NotFoundError: If announcement not found
            ValidationError: If the data is invalid
        """
        # Get the announcement
        announcement = await self._get_announcement_by_id(announcement_id)
        
        # Track the previous status
        previous_status = announcement.status
        
        # Update the announcement fields
        update_data = data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            if key in ["type", "status"] and value is not None:
                # Convert enum to value for database
                setattr(announcement, key, value.value)
            elif value is not None:
                setattr(announcement, key, value)
        
        try:
            # Save changes
            await self.db.commit()
            await self.db.refresh(announcement)
            
            # If status changed to published, send notifications
            if previous_status != AnnouncementStatus.PUBLISHED.value and announcement.status == AnnouncementStatus.PUBLISHED.value:
                await self._send_announcement_notifications(announcement)
                
            return AnnouncementResponse.model_validate(announcement)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update announcement: {str(e)}")
            raise ValidationError(f"Failed to update announcement: {str(e)}")
    
    async def delete_announcement(self, announcement_id: UUID) -> None:
        """Delete an announcement.
        
        Args:
            announcement_id: ID of the announcement
            
        Raises:
            NotFoundError: If announcement not found
        """
        # Get the announcement
        announcement = await self._get_announcement_by_id(announcement_id)
        
        try:
            # Delete the announcement
            await self.db.delete(announcement)
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete announcement: {str(e)}")
            raise ValidationError(f"Failed to delete announcement: {str(e)}")
    
    async def publish_announcement(
        self,
        announcement_id: UUID,
        user_id: UUID
    ) -> AnnouncementResponse:
        """Publish an announcement and send notifications.
        
        Args:
            announcement_id: ID of the announcement
            user_id: ID of the user publishing the announcement
            
        Returns:
            Published announcement
            
        Raises:
            NotFoundError: If announcement not found
            ValidationError: If the announcement cannot be published
        """
        # Get the announcement
        announcement = await self._get_announcement_by_id(announcement_id)
        
        # Check if already published
        if announcement.status == AnnouncementStatus.PUBLISHED.value:
            raise ValidationError("Announcement is already published")
        
        try:
            # Update status to published
            announcement.status = AnnouncementStatus.PUBLISHED.value
            
            # Save changes
            await self.db.commit()
            await self.db.refresh(announcement)
            
            # Send notifications
            await self._send_announcement_notifications(announcement)
            
            return AnnouncementResponse.model_validate(announcement)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to publish announcement: {str(e)}")
            raise ValidationError(f"Failed to publish announcement: {str(e)}")
    
    async def _get_announcement_by_id(self, announcement_id: UUID) -> Announcement:
        """Get an announcement by ID.
        
        Args:
            announcement_id: ID of the announcement
            
        Returns:
            Announcement
            
        Raises:
            NotFoundError: If announcement not found
        """
        result = await self.db.execute(
            select(Announcement)
            .options(selectinload(Announcement.creator))
            .filter(Announcement.id == announcement_id)
        )
        announcement = result.scalar_one_or_none()
        
        if not announcement:
            raise NotFoundError(f"Announcement with ID {announcement_id} not found")
            
        return announcement
    
    async def _send_announcement_notifications(self, announcement: Announcement) -> None:
        """Send notifications for an announcement.
        
        Args:
            announcement: The announcement to send notifications for
        """
        try:
            # Import here to avoid circular imports
            from core.notifications import TemplatedNotificationService
            
            notification_service = TemplatedNotificationService(self.db)
            
            # Define which notification template to use based on announcement type
            template_map = {
                AnnouncementType.FEATURE.value: "feature_announcement",
                AnnouncementType.MAINTENANCE.value: "system_maintenance",
                AnnouncementType.PROMOTION.value: "special_promotion",
                AnnouncementType.NEWS.value: "system_announcement",
                AnnouncementType.OTHER.value: "system_announcement"
            }
            
            template_id = template_map.get(announcement.type, "system_announcement")
            
            # Prepare notification parameters
            template_params = {
                "announcement_title": announcement.title,
                "announcement_content": announcement.content
            }
            
            # Add action URL and text if available
            if announcement.action_url:
                template_params["action_url"] = announcement.action_url
                template_params["action_text"] = announcement.action_text or "Learn More"
            
            # Prepare metadata
            metadata = {
                "announcement_id": str(announcement.id),
                "announcement_type": announcement.type,
                "is_important": announcement.is_important,
            }
            
            # Add any custom metadata from the announcement
            if announcement.announcement_metadata:
                metadata.update(announcement.announcement_metadata)
            
            # Query users to notify based on target groups
            target_groups = announcement.target_user_groups
            
            if not target_groups:  # Empty list means all users
                # Get all active users
                query = select(User.id).filter(User.status == "active")
            else:
                # Only notify users in specified groups
                # Here we would need to implement logic to filter by user groups
                # For now, just notify all users
                query = select(User.id).filter(User.status == "active")
            
            result = await self.db.execute(query)
            user_ids = result.scalars().all()
            
            # Send notifications to all target users
            for user_id in user_ids:
                try:
                    await notification_service.send_notification(
                        template_id=template_id,
                        user_id=user_id,
                        template_params=template_params,
                        metadata=metadata,
                        action_url=announcement.action_url
                    )
                except Exception as inner_error:
                    # Log but continue with other users
                    logger.warning(f"Failed to send announcement notification to user {user_id}: {str(inner_error)}")
            
            logger.info(f"Sent announcement notifications for announcement {announcement.id} to {len(user_ids)} users")
            
        except Exception as e:
            logger.error(f"Failed to send announcement notifications: {str(e)}")
            # We don't re-raise here to avoid failing the entire operation if notifications fail
    
    async def check_scheduled_announcements(self) -> int:
        """Check for scheduled announcements that should be published.
        
        This method is intended to be called by a scheduled task.
        
        Returns:
            Number of announcements published
        """
        try:
            now = datetime.utcnow()
            
            # Find scheduled announcements that should be published now
            query = select(Announcement).filter(
                and_(
                    Announcement.status == AnnouncementStatus.SCHEDULED.value,
                    Announcement.publish_at <= now
                )
            )
            
            result = await self.db.execute(query)
            announcements = result.scalars().all()
            
            published_count = 0
            
            # Publish each announcement
            for announcement in announcements:
                try:
                    # Update status to published
                    announcement.status = AnnouncementStatus.PUBLISHED.value
                    
                    # Send notifications
                    await self._send_announcement_notifications(announcement)
                    
                    published_count += 1
                    
                except Exception as inner_error:
                    # Log but continue with other announcements
                    logger.error(f"Failed to publish scheduled announcement {announcement.id}: {str(inner_error)}")
            
            # Commit all changes
            if published_count > 0:
                await self.db.commit()
                
            return published_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to check scheduled announcements: {str(e)}")
            return 0
    
    async def archive_expired_announcements(self) -> int:
        """Archive announcements that have passed their expiration date.
        
        This method is intended to be called by a scheduled task.
        
        Returns:
            Number of announcements archived
        """
        try:
            now = datetime.utcnow()
            
            # Find published announcements that have expired
            query = select(Announcement).filter(
                and_(
                    Announcement.status == AnnouncementStatus.PUBLISHED.value,
                    Announcement.expire_at.isnot(None),
                    Announcement.expire_at <= now
                )
            )
            
            result = await self.db.execute(query)
            announcements = result.scalars().all()
            
            # Update status to archived
            for announcement in announcements:
                announcement.status = AnnouncementStatus.ARCHIVED.value
            
            # Commit all changes
            if announcements:
                await self.db.commit()
                
            return len(announcements)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to archive expired announcements: {str(e)}")
            return 0 