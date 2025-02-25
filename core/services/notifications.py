"""Notification service module.

This module provides the notification service for handling all notification-related operations,
including preferences management and multi-channel delivery.
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
import json
import logging
from sqlalchemy import select, update, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp
from fastapi import BackgroundTasks

from core.models.notification import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationResponse
)
from core.models.user_preferences import (
    NotificationPreferencesBase as NotificationPreferences,
    NotificationFrequency,
    NotificationTimeWindow
)
from core.models.user import User
from core.utils.redis import get_redis_client
from core.utils.templates import render_template
from core.services.email import email_service
from core.exceptions import (
    NotificationError,
    NotificationNotFoundError,
    NotificationDeliveryError,
    NotificationRateLimitError,
    InvalidNotificationTemplateError
)
from core.config import settings
from core.database import get_async_db_session
from core.logger import logger

logger = logging.getLogger(__name__)

# In-memory storage for notifications (temporary solution)
notifications_store = {}

async def create_notification(notification_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a notification for WebSocket delivery.
    
    This is a simplified version of the notification creation process
    specifically for WebSocket notifications.
    """
    try:
        # Generate notification ID if not provided
        notification_id = notification_data.get("id", str(uuid4()))
        
        # Create notification with required fields
        notification = {
            "id": notification_id,
            "user_id": notification_data["user_id"],
            "title": notification_data.get("title", "New Notification"),
            "message": notification_data.get("message", ""),
            "type": notification_data.get("type", "general"),
            "read": False,
            "created_at": datetime.utcnow().isoformat(),
            "priority": notification_data.get("priority", "medium"),
            "action_url": notification_data.get("action_url")
        }
        
        # Store in memory
        notifications_store[notification_id] = notification
        
        return notification
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        raise NotificationError(f"Failed to create notification: {str(e)}")

class NotificationService:
    """Service for handling notifications."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._background_tasks = None
        self._fcm_config = {
            "endpoint": settings.FCM_ENDPOINT,
            "api_key": settings.FCM_API_KEY
        }
        self._email_config = {
            "from_email": settings.EMAIL_FROM,
            "template_dir": "templates/email"
        }

    async def __aenter__(self):
        """Async context manager enter."""
        if not self.db:
            self.db = await get_async_db_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.db:
            await self.db.close()

    async def get_db(self) -> AsyncSession:
        """Get database session."""
        if not self.db:
            self.db = await get_async_db_session()
        return self.db

    def set_background_tasks(self, background_tasks: Optional[BackgroundTasks]) -> None:
        """Set the background tasks instance.
        
        Args:
            background_tasks: FastAPI BackgroundTasks instance
        """
        self._background_tasks = background_tasks

    def add_background_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        """Add a task to be executed in the background.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Raises:
            ValueError: If background_tasks is not initialized
        """
        if self._background_tasks is None:
            raise ValueError("Background tasks not initialized")
        self._background_tasks.add_task(func, *args, **kwargs)

    async def get_user_preferences(self, user_id: UUID) -> NotificationPreferences:
        """Get user's notification preferences"""
        query = select(NotificationPreferences).where(
            NotificationPreferences.user_id == user_id
        )
        result = await self.db.execute(query)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences if none exist
            preferences = NotificationPreferences(user_id=user_id)
            self.db.add(preferences)
            await self.db.commit()
            await self.db.refresh(preferences)

        return preferences

    async def update_preferences(
        self,
        user_id: UUID,
        preferences_data: Dict[str, Any]
    ) -> NotificationPreferences:
        """Update user's notification preferences"""
        preferences = await self.get_user_preferences(user_id)
        
        for key, value in preferences_data.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)

        await self.db.commit()
        await self.db.refresh(preferences)
        return preferences

    async def should_send_notification(
        self,
        notification: Notification,
        preferences: NotificationPreferences,
        channel: NotificationChannel
    ) -> Tuple[bool, Optional[str]]:
        """Check if notification should be sent based on preferences"""
        # Check if channel is enabled
        if channel.value not in preferences.enabled_channels:
            return False, "Channel disabled"

        # Check do not disturb
        if preferences.do_not_disturb:
            return False, "Do not disturb enabled"

        # Check muted status
        if preferences.muted_until and datetime.now().time() < preferences.muted_until:
            return False, "Notifications muted"

        # Check time window
        time_window = preferences.time_windows.get(channel.value)
        if time_window:
            current_time = datetime.now().time()
            if not (time_window["start_time"] <= current_time <= time_window["end_time"]):
                return False, "Outside time window"

        # Check frequency
        frequency = preferences.notification_frequency.get(notification.type)
        if frequency == NotificationFrequency.DAILY.value:
            # Check if already sent today
            sent_today = await self._check_sent_today(notification.user_id, notification.type)
            if sent_today:
                return False, "Daily limit reached"

        # Check minimum priority
        if notification.priority < preferences.minimum_priority:
            return False, "Below minimum priority"

        return True, None

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        type: NotificationType,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NotificationResponse:
        """Create a new notification.
        
        Args:
            user_id: User ID
            title: Notification title
            message: Notification message
            type: Notification type
            priority: Notification priority
            metadata: Optional metadata
            
        Returns:
            NotificationResponse: Created notification details
            
        Raises:
            NotificationError: If notification creation fails
        """
        try:
            # Get user preferences
            preferences = await self.get_user_preferences(user_id)

            # Create notification
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                priority=priority,
                metadata=metadata,
                status=NotificationStatus.PENDING
            )

            self.db.add(notification)
            await self.db.commit()
            await self.db.refresh(notification)

            # Process notification delivery in background if tasks are available
            if self._background_tasks is not None:
                if metadata and metadata.get("schedule_for"):
                    self.add_background_task(
                        self._schedule_notification_delivery,
                        notification,
                        preferences
                    )
                else:
                    self.add_background_task(
                        self._process_notification_delivery,
                        notification,
                        preferences
                    )

            # Convert to response model
            return NotificationResponse(
                id=notification.id,
                user_id=notification.user_id,
                goal_id=notification.goal_id,
                deal_id=notification.deal_id,
                title=notification.title,
                message=notification.message,
                type=notification.type,
                channels=notification.channels,
                priority=notification.priority,
                data=notification.data,
                notification_metadata=notification.metadata,
                action_url=notification.action_url,
                status=notification.status,
                created_at=notification.created_at,
                schedule_for=notification.schedule_for,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                read_at=notification.read_at,
                error=notification.error
            )

        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            raise NotificationError(f"Failed to create notification: {str(e)}")

    async def _process_notification_delivery(
        self,
        notification: Notification,
        preferences: NotificationPreferences
    ) -> None:
        """Process notification delivery through enabled channels"""
        for channel in notification.channels:
            should_send, reason = await self.should_send_notification(
                notification,
                preferences,
                channel
            )

            if not should_send:
                logger.info(
                    f"Skipping {channel} notification for user {notification.user_id}: {reason}"
                )
                continue

            try:
                if channel == NotificationChannel.EMAIL:
                    await self._send_email_notification(notification)
                elif channel == NotificationChannel.PUSH:
                    await self._send_push_notification(notification)
                elif channel == NotificationChannel.SMS:
                    await self._send_sms_notification(notification)
                elif channel == NotificationChannel.IN_APP:
                    await self._send_in_app_notification(notification)

                notification.status = NotificationStatus.SENT
                await self.db.commit()

            except Exception as e:
                logger.error(
                    f"Error sending {channel} notification: {str(e)}"
                )
                notification.error = str(e)
                notification.status = NotificationStatus.FAILED
                await self.db.commit()

    async def _send_push_notification(self, notification: Notification) -> None:
        """Send push notification using Firebase Cloud Messaging"""
        try:
            # Get user's push tokens
            user = await self.db.get(User, notification.user_id)
            if not user or not user.push_tokens:
                raise NotificationDeliveryError("No push tokens found for user")

            # Prepare notification payload
            payload = {
                "notification": {
                    "title": notification.title,
                    "body": notification.message,
                    "click_action": notification.action_url
                },
                "data": {
                    "notification_id": str(notification.id),
                    "type": notification.type,
                    **(notification.data if notification.data else {})
                }
            }

            # Send to each device token
            async with aiohttp.ClientSession() as session:
                for token in user.push_tokens:
                    try:
                        payload["to"] = token
                        async with session.post(
                            self._fcm_config["endpoint"],
                            json=payload,
                            headers={
                                "Authorization": f"key={self._fcm_config['api_key']}",
                                "Content-Type": "application/json"
                            }
                        ) as response:
                            if response.status != 200:
                                logger.error(f"FCM request failed: {await response.text()}")
                    except Exception as e:
                        logger.error(f"Error sending to token {token}: {str(e)}")

        except Exception as e:
            logger.error(f"Push notification failed: {str(e)}")
            raise NotificationDeliveryError(f"Push notification failed: {str(e)}")

    async def _send_email_notification(self, notification: Notification) -> None:
        """Send email notification"""
        try:
            # Get user email
            user = await self.db.get(User, notification.user_id)
            if not user or not user.email:
                raise NotificationDeliveryError("No email found for user")

            # Prepare email context
            context = {
                "title": notification.title,
                "message": notification.message,
                "action_url": notification.action_url,
                "data": notification.data,
                "year": datetime.now().year,
                "unsubscribe_url": f"/notifications/preferences"
            }

            # Send email using email service
            template_name = f"{notification.type.lower()}_email.html"
            success = await email_service.send_email(
                to_email=user.email,
                subject=notification.title,
                template_name=template_name,
                template_data=context,
                from_email=self._email_config["from_email"]
            )

            if not success:
                raise NotificationDeliveryError("Failed to send email")

        except Exception as e:
            logger.error(f"Email notification failed: {str(e)}")
            raise NotificationDeliveryError(f"Email notification failed: {str(e)}")

    async def _send_in_app_notification(self, notification: Notification) -> None:
        """Store in-app notification"""
        try:
            # Update notification status
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()
            await self.db.commit()
            
            # Broadcast to connected WebSocket clients if any
            from core.api.v1.notifications.websocket import notification_manager
            await notification_manager.broadcast_to_user(
                str(notification.user_id),
                notification.to_dict()
            )
            
        except Exception as e:
            logger.error(f"In-app notification failed: {str(e)}")
            raise NotificationDeliveryError(f"In-app notification failed: {str(e)}")

    async def _send_sms_notification(self, notification: Notification) -> None:
        """Send SMS notification"""
        try:
            # Get user phone
            user = await self.db.get(User, notification.user_id)
            if not user or not user.phone:
                raise NotificationDeliveryError("No phone number found for user")

            # TODO: Implement SMS sending logic
            logger.warning("SMS notifications not implemented yet")
            
        except Exception as e:
            logger.error(f"SMS notification failed: {str(e)}")
            raise NotificationDeliveryError(f"SMS notification failed: {str(e)}")

    async def _check_sent_today(self, user_id: UUID, notification_type: str) -> bool:
        """Check if notification of given type was sent today"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == notification_type,
            Notification.created_at >= today_start,
            Notification.status == NotificationStatus.SENT
        )
        result = await self.db.execute(query)
        return bool(result.first())

    async def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None
    ) -> List[NotificationResponse]:
        """Get user notifications with filtering options."""
        try:
            # Ensure we have a database session
            if not self.db:
                self.db = await get_async_db_session()

            # Build base query
            stmt = select(Notification).where(Notification.user_id == user_id)

            # Apply filters
            if unread_only:
                stmt = stmt.where(Notification.read_at.is_(None))
            if notification_type:
                stmt = stmt.where(Notification.type == notification_type)

            # Add ordering and pagination
            stmt = stmt.order_by(desc(Notification.created_at))
            stmt = stmt.offset(offset).limit(limit)

            # Execute query
            result = await self.db.execute(stmt)
            notifications = result.scalars().all()

            # Convert to response models
            return [
                NotificationResponse.model_validate({
                    "id": n.id,
                    "user_id": n.user_id,
                    "goal_id": n.goal_id,
                    "deal_id": n.deal_id,
                    "title": n.title,
                    "message": n.message,
                    "type": n.type,
                    "channels": n.channels,
                    "priority": n.priority,
                    "data": n.data,
                    "notification_metadata": n.metadata,
                    "action_url": n.action_url,
                    "status": n.status,
                    "created_at": n.created_at,
                    "schedule_for": n.schedule_for,
                    "sent_at": n.sent_at,
                    "delivered_at": n.delivered_at,
                    "read_at": n.read_at,
                    "error": n.error
                }) for n in notifications
            ]

        except Exception as e:
            logger.error(f"Failed to get user notifications: {str(e)}")
            raise NotificationError("Failed to retrieve notifications") from e

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications"""
        try:
            db = await self.get_db()
            query = select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None)
                )
            )
            result = await db.execute(query)
            return len(list(result.scalars().all()))
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0

    async def delete_notifications(
        self,
        notification_ids: List[str],
        user_id: UUID
    ) -> None:
        """Delete notifications"""
        query = select(Notification).where(
            Notification.id.in_(notification_ids),
            Notification.user_id == user_id
        )
        result = await self.db.execute(query)
        notifications = result.scalars().all()

        for notification in notifications:
            await self.db.delete(notification)

        await self.db.commit()

    async def clear_all_notifications(self, user_id: UUID) -> None:
        """Clear all notifications for a user"""
        query = select(Notification).where(Notification.user_id == user_id)
        result = await self.db.execute(query)
        notifications = result.scalars().all()

        for notification in notifications:
            await self.db.delete(notification)

        await self.db.commit()

    async def mark_as_read(self, notification_ids: List[str], user_id: str) -> List[Notification]:
        """Mark notifications as read."""
        try:
            query = select(Notification).where(
                Notification.id.in_(notification_ids),
                Notification.user_id == user_id
            )
            result = await self.db.execute(query)
            notifications = result.scalars().all()

            for notification in notifications:
                notification.read = True
                notification.read_at = datetime.utcnow()

            await self.db.commit()
            return notifications

        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            raise NotificationError(f"Failed to mark notifications as read: {str(e)}")

    async def _schedule_notification_delivery(
        self,
        notification: Notification,
        preferences: NotificationPreferences
    ) -> None:
        """Schedule notification delivery for later processing.
        
        Args:
            notification: The notification to schedule
            preferences: User notification preferences
        """
        try:
            # Get Redis client
            redis = await get_redis_client()
            if not redis:
                logger.warning("Redis not available, processing notification immediately")
                await self._process_notification_delivery(notification, preferences)
                return

            # Schedule notification for processing
            schedule_time = notification.metadata.get("schedule_for")
            if not schedule_time:
                logger.warning("No schedule time found, processing immediately")
                await self._process_notification_delivery(notification, preferences)
                return

            # Store notification data in Redis
            notification_data = {
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id),
                "preferences": preferences.dict()
            }
            
            key = f"scheduled_notification:{notification.id}"
            await redis.set(
                key,
                json.dumps(notification_data),
                ex=int((datetime.fromisoformat(schedule_time) - datetime.now()).total_seconds())
            )
            
            logger.info(f"Scheduled notification {notification.id} for {schedule_time}")
            
        except Exception as e:
            logger.error(f"Failed to schedule notification: {str(e)}")
            # Fall back to immediate processing
            await self._process_notification_delivery(notification, preferences)

    async def send_verification_email(self, email: str, token: str) -> None:
        """Send email verification link to user.
        
        Args:
            email: User's email address
            token: Verification token
            
        Raises:
            NotificationError: If sending verification email fails
        """
        try:
            verification_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
            
            # Prepare email context
            context = {
                "verification_url": verification_url,
                "year": datetime.utcnow().year
            }
            
            # Send email using email service
            success = await email_service.send_email(
                to_email=email,
                subject="Verify Your Email Address",
                template_name="verification.html",
                template_data=context,
                from_email=self._email_config["from_email"]
            )

            if not success:
                raise NotificationError("Failed to send verification email")

            logger.info(f"Verification email sent to {email}")
            
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            raise NotificationError(f"Failed to send verification email: {str(e)}")

# Create a global instance of the notification service
notification_service = NotificationService(None)  # Session will be injected per request 

class Config:
    """Pydantic config."""
    arbitrary_types_allowed = True 