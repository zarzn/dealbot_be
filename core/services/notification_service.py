"""Notification service module."""

from typing import Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.models.database import Notification
from core.exceptions.base_exceptions import NotificationError
from core.utils.redis import RedisClient

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling notifications."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize notification service."""
        self.session = session
        self.redis = RedisClient()

    async def send_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: str = "in_app",
        data: Optional[Dict[str, Any]] = None,
        priority: bool = False
    ) -> Notification:
        """Send a notification to a user."""
        try:
            # Create notification record
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=notification_type,
                priority=1 if priority else 0,
                data=data
            )

            if self.session:
                self.session.add(notification)
                await self.session.commit()
                await self.session.refresh(notification)

            # Cache notification
            await self.redis.set(
                f"notification:{notification.id}",
                {
                    "id": str(notification.id),
                    "user_id": str(notification.user_id),
                    "title": notification.title,
                    "message": notification.message,
                    "type": notification.type,
                    "priority": notification.priority,
                    "data": notification.data,
                    "created_at": notification.created_at.isoformat()
                },
                ex=3600  # 1 hour
            )

            # Add to user's notification list
            await self.redis.lpush(
                f"user:{user_id}:notifications",
                str(notification.id)
            )

            return notification

        except Exception as e:
            if self.session:
                await self.session.rollback()
            logger.error(f"Error sending notification: {str(e)}")
            raise NotificationError(f"Failed to send notification: {str(e)}")

    async def send_email_notification(self, notification: Notification) -> None:
        """Send an email notification."""
        # TODO: Implement email sending logic
        notification.sent_at = datetime.utcnow()

    async def send_push_notification(self, notification: Notification) -> None:
        """Send a push notification."""
        # TODO: Implement push notification logic
        notification.sent_at = datetime.utcnow()

    async def send_sms_notification(self, notification: Notification) -> None:
        """Send an SMS notification."""
        # TODO: Implement SMS sending logic
        notification.sent_at = datetime.utcnow()

    async def get_user_notifications(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> list[Notification]:
        """Get notifications for a user."""
        try:
            if not self.session:
                raise NotificationError("Database session not available")

            result = await self.session.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}")
            raise NotificationError(f"Failed to get notifications: {str(e)}")

    async def mark_as_read(self, notification_id: UUID) -> None:
        """Mark a notification as read."""
        try:
            if not self.session:
                raise NotificationError("Database session not available")

            notification = await self.session.get(Notification, notification_id)
            if notification:
                notification.read_at = datetime.utcnow()
                await self.session.commit()

        except Exception as e:
            if self.session:
                await self.session.rollback()
            logger.error(f"Error marking notification as read: {str(e)}")
            raise NotificationError(f"Failed to mark notification as read: {str(e)}")

    async def delete_notification(self, notification_id: UUID) -> None:
        """Delete a notification."""
        try:
            if not self.session:
                raise NotificationError("Database session not available")

            notification = await self.session.get(Notification, notification_id)
            if notification:
                await self.session.delete(notification)
                await self.session.commit()

                # Remove from cache
                await self.redis.delete(f"notification:{notification_id}")
                await self.redis.lrem(
                    f"user:{notification.user_id}:notifications",
                    0,
                    str(notification_id)
                )

        except Exception as e:
            if self.session:
                await self.session.rollback()
            logger.error(f"Error deleting notification: {str(e)}")
            raise NotificationError(f"Failed to delete notification: {str(e)}") 