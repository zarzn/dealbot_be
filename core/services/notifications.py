"""Notification service module.

This module provides the notification service for handling all notification-related operations,
including preferences management and multi-channel delivery.
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp
from fastapi import BackgroundTasks

from core.models.notification import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus
)
from core.models.notification_preferences import (
    NotificationPreferences,
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

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling notifications and preferences"""

    def __init__(self, session: AsyncSession, background_tasks: Optional[BackgroundTasks] = None):
        self.session = session
        self.background_tasks = background_tasks
        self._email_config = {
            "from_email": "deals@yourdomain.com",
            "template_dir": "templates/email"
        }
        self._fcm_config = {
            "api_key": "your-fcm-api-key",
            "endpoint": "https://fcm.googleapis.com/fcm/send"
        }

    async def get_user_preferences(self, user_id: UUID) -> NotificationPreferences:
        """Get user's notification preferences"""
        query = select(NotificationPreferences).where(
            NotificationPreferences.user_id == user_id
        )
        result = await self.session.execute(query)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences if none exist
            preferences = NotificationPreferences(user_id=user_id)
            self.session.add(preferences)
            await self.session.commit()
            await self.session.refresh(preferences)

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

        await self.session.commit()
        await self.session.refresh(preferences)
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
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
        notification_metadata: Optional[Dict[str, Any]] = None,
        action_url: Optional[str] = None,
        schedule_for: Optional[datetime] = None,
        deal_id: Optional[UUID] = None,
        goal_id: Optional[UUID] = None
    ) -> Notification:
        """Create and send a notification"""
        try:
            # Get user preferences
            preferences = await self.get_user_preferences(user_id)

            # Create notification
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                channels=channels or [NotificationChannel.IN_APP],
                priority=priority,
                data=data,
                notification_metadata=notification_metadata,
                action_url=action_url,
                schedule_for=schedule_for,
                deal_id=deal_id,
                goal_id=goal_id
            )

            self.session.add(notification)
            await self.session.commit()
            await self.session.refresh(notification)

            # Process notification delivery
            if not schedule_for or schedule_for <= datetime.now():
                if self.background_tasks:
                    self.background_tasks.add_task(
                        self._process_notification_delivery,
                        notification,
                        preferences
                        )
                    else:
                    await self._process_notification_delivery(notification, preferences)

            return notification

        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
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
                await self.session.commit()

            except Exception as e:
                logger.error(
                    f"Error sending {channel} notification: {str(e)}"
                )
                notification.error = str(e)
                notification.status = NotificationStatus.FAILED
                await self.session.commit()

    async def _send_push_notification(self, notification: Notification) -> None:
        """Send push notification using Firebase Cloud Messaging"""
        try:
            # Get user's push tokens
            user = await self.session.get(User, notification.user_id)
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
            user = await self.session.get(User, notification.user_id)
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
            await self.session.commit()
            
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
            user = await self.session.get(User, notification.user_id)
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
        result = await self.session.execute(query)
        return bool(result.first())

    async def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None
    ) -> List[Notification]:
        """Get user's notifications with pagination"""
        query = select(Notification).where(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc())

        if unread_only:
            query = query.where(Notification.read_at.is_(None))

        if notification_type:
            query = query.where(Notification.type == notification_type)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications"""
        query = select(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None)
        )
        result = await self.session.execute(query)
        return len(list(result.scalars().all()))

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
        result = await self.session.execute(query)
        notifications = result.scalars().all()

        for notification in notifications:
            await self.session.delete(notification)

        await self.session.commit()

    async def clear_all_notifications(self, user_id: UUID) -> None:
        """Clear all notifications for a user"""
        query = select(Notification).where(Notification.user_id == user_id)
        result = await self.session.execute(query)
        notifications = result.scalars().all()

        for notification in notifications:
            await self.session.delete(notification)

        await self.session.commit()

# Create a global instance of the notification service
notification_service = NotificationService(None)  # Session will be injected per request 