from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging

from core.models.notification import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus
)
from core.models.user import User
from core.utils.redis import get_redis_client
from core.exceptions.notification_exceptions import (
    NotificationError,
    NotificationNotFoundError,
    NotificationDeliveryError
)
from core.exceptions.base_exceptions import BaseError
""" from core.exceptions import (
    NotificationError,
    NotificationNotFoundError,
    NotificationDeliveryError,
    NotificationRateLimitError,
    InvalidNotificationTemplateError,
    APIServiceUnavailableError,
    CacheOperationError,
    DatabaseError,
    ValidationError,
    NetworkError,
    DataProcessingError,
    RepositoryError,
    UserNotFoundError,
    TokenError,
    RateLimitExceededError
) 
DO NOT DELETE THIS COMMENT
"""


class NotificationService:
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self._email_config = {
            "from_email": "deals@yourdomain.com",
            "template_dir": "templates/email"
        }

    async def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM,
        channels: List[NotificationChannel] = [NotificationChannel.IN_APP],
        data: Optional[Dict[str, Any]] = None,
        priority: bool = False
    ) -> Notification:
        """Send a notification to a user"""
        try:
            # Create notification record
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=notification_type,
                channels=channels,
                notification_metadata=data or {},
                priority=NotificationPriority.HIGH if priority else NotificationPriority.MEDIUM,
                created_at=datetime.utcnow()
            )

            if self.session:
                self.session.add(notification)
                await self.session.commit()
                await self.session.refresh(notification)

            # Send notification based on type
            if notification_type == NotificationType.EMAIL:
                await self._send_email_notification(notification)
            elif notification_type == NotificationType.PUSH:
                await self._send_push_notification(notification)
            elif notification_type == NotificationType.SMS:
                await self._send_sms_notification(notification)
            
            # Store in Redis for real-time access
            await self._cache_notification(notification)

            return notification

        except BaseError as e:
            if self.session:
                await self.session.rollback()
            raise NotificationError(f"Error sending notification: {str(e)}")

    async def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[Notification]:
        """Get notifications for a user"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            query = select(Notification).where(
                Notification.user_id == user_id
            )

            if unread_only:
                query = query.where(Notification.read_at.is_(None))

            query = query.order_by(Notification.created_at.desc())
            query = query.offset(offset).limit(limit)

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            raise NotificationNotFoundError(f"Error getting notifications: {str(e)}")

    async def mark_as_read(
        self,
        notification_ids: List[str],
        user_id: str
    ) -> List[Notification]:
        """Mark notifications as read"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            notifications = await self.session.execute(
                select(Notification).where(
                    Notification.id.in_(notification_ids),
                    Notification.user_id == user_id
                )
            )
            notifications = list(notifications.scalars().all())

            for notification in notifications:
                notification.read_at = datetime.utcnow()

            await self.session.commit()
            return notifications

        except Exception as e:
            await self.session.rollback()
            raise NotificationError(f"Error marking notifications as read: {str(e)}")

    async def _send_email_notification(self, notification: Notification) -> None:
        """Send email notification"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            # Get user email
            user = await self.session.get(User, notification.user_id)
            if not user or not user.email:
                raise NotificationNotFoundError("User email not found")

            # Prepare email data
            email_data = {
                "to_email": user.email,
                "subject": notification.title,
                "template": "notification.html",
                "context": {
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data
                }
            }

            # Send email using your email service
            # This is a placeholder - implement your email sending logic
            print(f"Sending email to {user.email}: {notification.title}")

        except Exception as e:
            raise NotificationError(f"Error sending email notification: {str(e)}")

    async def _send_push_notification(self, notification: Notification) -> None:
        """Send push notification"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            # Get user's push tokens
            user = await self.session.get(User, notification.user_id)
            if not user or not user.push_tokens:
                raise NotificationNotFoundError("User push tokens not found")

            # Prepare push notification data
            push_data = {
                "title": notification.title,
                "body": notification.message,
                "data": notification.data,
                "priority": "high" if notification.priority else "normal"
            }

            # Send to each device token
            async with aiohttp.ClientSession() as session:
                for token in user.push_tokens:
                    try:
                        # This is a placeholder - implement your push notification service
                        print(f"Sending push notification to token {token}: {notification.title}")
                    except Exception as e:
                        print(f"Error sending push notification to token {token}: {str(e)}")

        except Exception as e:
            raise NotificationError(f"Error sending push notification: {str(e)}")

    async def _send_sms_notification(self, notification: Notification) -> None:
        """Send SMS notification"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            # Get user's phone number
            user = await self.session.get(User, notification.user_id)
            if not user or not user.phone_number:
                raise NotificationNotFoundError("User phone number not found")

            # Prepare SMS data
            sms_data = {
                "to": user.phone_number,
                "message": f"{notification.title}\n\n{notification.message}"
            }

            # This is a placeholder - implement your SMS service
            print(f"Sending SMS to {user.phone_number}: {notification.title}")

        except Exception as e:
            raise NotificationError(f"Error sending SMS notification: {str(e)}")

    async def _cache_notification(self, notification: Notification) -> None:
        """Cache notification in Redis for real-time access"""
        try:
            redis = await get_redis_client()
            
            # Cache individual notification
            notification_key = f"notification:{notification.id}"
            notification_data = {
                "id": str(notification.id),
                "user_id": str(notification.user_id),
                "title": notification.title,
                "message": notification.message,
                "type": notification.type.value,
                "data": notification.data,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat(),
                "read_at": notification.read_at.isoformat() if notification.read_at else None
            }
            await redis.set(
                notification_key,
                json.dumps(notification_data),
                ex=86400  # 24 hours
            )

            # Add to user's recent notifications list
            user_notifications_key = f"user:{notification.user_id}:notifications"
            await redis.lpush(user_notifications_key, str(notification.id))
            await redis.ltrim(user_notifications_key, 0, 99)  # Keep last 100 notifications

        except Exception as e:
            print(f"Error caching notification: {str(e)}")

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            result = await self.session.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None)
                )
            )
            return len(list(result.scalars().all()))

        except Exception as e:
            raise NotificationError(f"Error getting unread count: {str(e)}")

    async def delete_notifications(
        self,
        notification_ids: List[str],
        user_id: str
    ) -> None:
        """Delete notifications"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            # Delete from database
            notifications = await self.session.execute(
                select(Notification).where(
                    Notification.id.in_(notification_ids),
                    Notification.user_id == user_id
                )
            )
            notifications = list(notifications.scalars().all())

            for notification in notifications:
                await self.session.delete(notification)

            await self.session.commit()

            # Delete from Redis
            redis = await get_redis_client()
            for notification_id in notification_ids:
                await redis.delete(f"notification:{notification_id}")

        except Exception as e:
            await self.session.rollback()
            raise NotificationError(f"Error deleting notifications: {str(e)}")

    async def clear_all_notifications(self, user_id: str) -> None:
        """Clear all notifications for a user"""
        if not self.session:
            raise NotificationNotFoundError("Database session required for this operation")

        try:
            # Delete from database
            notifications = await self.session.execute(
                select(Notification).where(Notification.user_id == user_id)
            )
            notifications = list(notifications.scalars().all())

            for notification in notifications:
                await self.session.delete(notification)

            await self.session.commit()

            # Clear from Redis
            redis = await get_redis_client()
            await redis.delete(f"user:{user_id}:notifications")

        except Exception as e:
            await self.session.rollback()
            raise NotificationError(f"Error clearing notifications: {str(e)}")

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        type: NotificationType,
        channels: List[NotificationChannel] = [NotificationChannel.IN_APP],
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
        notification_metadata: Optional[Dict[str, Any]] = None,
        action_url: Optional[str] = None,
        schedule_for: Optional[datetime] = None,
        deal_id: Optional[UUID] = None,
        goal_id: Optional[UUID] = None,
        expires_at: Optional[datetime] = None
    ) -> Notification:
        """Create a new notification"""
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                channels=channels,
                priority=priority,
                data=data,
                notification_metadata=notification_metadata,
                action_url=action_url,
                schedule_for=schedule_for,
                deal_id=deal_id,
                goal_id=goal_id,
                expires_at=expires_at
            )

            if self.session:
                self.session.add(notification)
                await self.session.commit()
                await self.session.refresh(notification)

            # Send notification based on type
            if type == NotificationType.EMAIL:
                await self._send_email_notification(notification)
            elif type == NotificationType.PUSH:
                await self._send_push_notification(notification)
            elif type == NotificationType.SMS:
                await self._send_sms_notification(notification)
            
            # Store in Redis for real-time access
            await self._cache_notification(notification)

            return notification

        except Exception as e:
            if self.session:
                await self.session.rollback()
            raise NotificationError(f"Error creating notification: {str(e)}") 
