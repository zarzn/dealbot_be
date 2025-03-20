"""Notification Service Module.

This module provides a high-level interface for sending notifications using templates.
It integrates with the core notification service while providing a simpler API.
"""

from typing import Dict, Any, List, Optional, Union
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.services.notification import NotificationService
from core.models.notification import (
    NotificationType,
    NotificationChannel,
    NotificationPriority
)
from core.notifications.factory import NotificationFactory

logger = logging.getLogger(__name__)

class TemplatedNotificationService:
    """Service for sending template-based notifications."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize with database session.
        
        Args:
            db_session: Database session to use for database operations
        """
        self.db = db_session
        self._notification_service = NotificationService(db_session)
    
    async def send_notification(
        self,
        template_id: str,
        user_id: UUID,
        template_params: Optional[Dict[str, Any]] = None,
        override_channels: Optional[List[NotificationChannel]] = None,
        override_priority: Optional[NotificationPriority] = None,
        metadata: Optional[Dict[str, Any]] = None,
        goal_id: Optional[UUID] = None,
        deal_id: Optional[UUID] = None,
        action_url: Optional[str] = None
    ) -> UUID:
        """Send a notification using a template.
        
        Args:
            template_id: ID of the template to use
            user_id: ID of the user to notify
            template_params: Parameters to format into the template message
            override_channels: Override default channels from template
            override_priority: Override default priority from template
            metadata: Additional metadata to merge with template defaults
            goal_id: Optional goal ID related to the notification
            deal_id: Optional deal ID related to the notification
            action_url: Optional override for action URL
            
        Returns:
            UUID of the created notification
        """
        try:
            # Generate notification parameters from template
            notification_params = NotificationFactory.create_notification(
                template_id=template_id,
                user_id=user_id,
                template_params=template_params,
                override_channels=override_channels,
                override_priority=override_priority,
                metadata=metadata,
                goal_id=goal_id,
                deal_id=deal_id,
                action_url=action_url
            )
            
            # Log the notification creation attempt
            logger.info(
                f"Creating notification from template {template_id} for user {user_id}"
            )
            
            # Create the notification using the notification service
            notification_id = await self._notification_service.create_notification(
                **notification_params
            )
            
            logger.info(f"Successfully created notification {notification_id}")
            return notification_id
            
        except Exception as e:
            logger.error(f"Error creating notification from template: {str(e)}")
            # If there's an error, attempt to create a fallback notification
            try:
                fallback_id = await self._notification_service.create_notification(
                    user_id=user_id,
                    title="System Notification",
                    message="An important notification could not be properly formatted.",
                    notification_type=NotificationType.SYSTEM,
                    channels=[NotificationChannel.IN_APP],
                    priority=NotificationPriority.MEDIUM,
                    notification_metadata={
                        "error": True,
                        "original_template": template_id,
                        "error_message": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                logger.info(f"Created fallback notification {fallback_id}")
                return fallback_id
            except Exception as fallback_error:
                logger.critical(f"Failed to create fallback notification: {str(fallback_error)}")
                raise

    # Convenience methods for common notification types
    
    async def send_system_notification(
        self,
        user_id: UUID,
        template_id: str,
        template_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> UUID:
        """Send a system notification."""
        return await self.send_notification(
            template_id=template_id,
            user_id=user_id,
            template_params=template_params,
            **kwargs
        )
    
    async def send_security_notification(
        self,
        user_id: UUID,
        template_id: str,
        template_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> UUID:
        """Send a security notification with high priority."""
        return await self.send_notification(
            template_id=template_id,
            user_id=user_id,
            template_params=template_params,
            override_priority=NotificationPriority.CRITICAL,
            **kwargs
        )
    
    async def send_deal_notification(
        self,
        user_id: UUID,
        template_id: str,
        deal_id: UUID,
        template_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> UUID:
        """Send a deal-related notification."""
        return await self.send_notification(
            template_id=template_id,
            user_id=user_id,
            template_params=template_params,
            deal_id=deal_id,
            **kwargs
        )
    
    async def send_goal_notification(
        self,
        user_id: UUID,
        template_id: str,
        goal_id: UUID,
        template_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> UUID:
        """Send a goal-related notification."""
        return await self.send_notification(
            template_id=template_id,
            user_id=user_id,
            template_params=template_params,
            goal_id=goal_id,
            **kwargs
        )
        
    # Helper methods for specific notifications
    
    async def send_password_changed_notification(
        self,
        user_id: UUID,
        **kwargs
    ) -> UUID:
        """Send a notification about password change."""
        return await self.send_security_notification(
            user_id=user_id,
            template_id="sec_password_changed",
            **kwargs
        )
    
    async def send_password_reset_notification(
        self,
        user_id: UUID,
        **kwargs
    ) -> UUID:
        """Send a notification about password reset."""
        return await self.send_security_notification(
            user_id=user_id,
            template_id="sec_password_reset",
            **kwargs
        )
    
    async def send_new_device_login_notification(
        self,
        user_id: UUID,
        device_type: str,
        location: str,
        **kwargs
    ) -> UUID:
        """Send a notification about login from a new device."""
        return await self.send_security_notification(
            user_id=user_id,
            template_id="sec_new_device_login",
            template_params={
                "device_type": device_type,
                "location": location
            },
            **kwargs
        )
        
    async def send_registration_confirmation(
        self,
        user_id: UUID,
        **kwargs
    ) -> UUID:
        """Send a welcome notification for new user registration."""
        return await self.send_system_notification(
            user_id=user_id,
            template_id="sys_registration_confirmation",
            **kwargs
        ) 