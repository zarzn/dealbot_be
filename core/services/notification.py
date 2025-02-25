"""Notification service module.

This module provides the notification service for handling all notification-related operations,
including preferences management and multi-channel delivery.
"""

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, time
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func, delete
import json
import logging
import traceback
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
    UserPreferences,
    NotificationPreferencesBase,
    NotificationFrequency,
    NotificationTimeWindow,
    Theme,
    Language,
    UserPreferencesResponse
)
from core.models.user import User
from core.utils.redis import RedisClient
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

class NotificationService:
    """Service for handling notifications."""

    def __init__(self, session: AsyncSession):
        """Initialize service with database session."""
        if not session:
            raise NotificationError("Database session is required")
        self.session = session
        self._background_tasks = None
        self._fcm_config = {
            "endpoint": settings.FCM_ENDPOINT,
            "api_key": settings.FCM_API_KEY
        }
        self._email_config = {
            "from_email": settings.EMAIL_FROM,
            "template_dir": "templates/email"
        }
        self._redis_client = None
        self._redis_enabled = False

    async def initialize_redis(self):
        """Initialize Redis client if not already initialized."""
        if not self._redis_client:
            try:
                self._redis_client = await RedisClient()
                self._redis_enabled = True
            except Exception as e:
                logger.warning(f"Redis not available, notifications will not be cached: {str(e)}")
                self._redis_enabled = False

    def _convert_to_response(self, notification: Notification) -> NotificationResponse:
        """Convert SQLAlchemy notification model to response model."""
        try:
            if not notification:
                raise NotificationError("Cannot convert None to NotificationResponse")
            
            return NotificationResponse(
                id=notification.id,
                user_id=notification.user_id,
                goal_id=notification.goal_id if notification.goal_id else None,
                deal_id=notification.deal_id if notification.deal_id else None,
                title=notification.title,
                message=notification.message,
                type=NotificationType(notification.type),
                channels=[NotificationChannel(ch) for ch in notification.channels],
                priority=NotificationPriority(notification.priority),
                notification_metadata=notification.notification_metadata or {},
                action_url=notification.action_url,
                status=NotificationStatus(notification.status),
                created_at=notification.created_at,
                schedule_for=notification.schedule_for,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                read_at=notification.read_at,
                error=notification.error
            )
        except Exception as e:
            logger.error(f"Error converting notification to response: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to convert notification to response: {str(e)}")

    def _convert_notification_frequency(self, freq_dict: Dict[str, Dict[str, str]]) -> Dict[NotificationType, NotificationFrequency]:
        """Convert notification frequency from database format to model format."""
        result = {}
        try:
            for key, value in freq_dict.items():
                try:
                    notification_type = NotificationType(key)
                    frequency = NotificationFrequency(value.get("frequency", "immediate"))
                    result[notification_type] = frequency
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid notification frequency format for {key}: {str(e)}")
                    # Use default value
                    result[NotificationType(key)] = NotificationFrequency.IMMEDIATE
        except Exception as e:
            logger.error(f"Error converting notification frequency: {str(e)}\n{traceback.format_exc()}")
            # Return default frequencies
            return {
                NotificationType.DEAL: NotificationFrequency.IMMEDIATE,
                NotificationType.GOAL: NotificationFrequency.IMMEDIATE,
                NotificationType.PRICE_ALERT: NotificationFrequency.IMMEDIATE,
                NotificationType.TOKEN: NotificationFrequency.DAILY,
                NotificationType.SECURITY: NotificationFrequency.IMMEDIATE,
                NotificationType.MARKET: NotificationFrequency.DAILY,
                NotificationType.SYSTEM: NotificationFrequency.IMMEDIATE
            }
        return result

    def _convert_time_windows(self, windows_dict: Dict[str, Dict[str, str]]) -> Dict[NotificationChannel, NotificationTimeWindow]:
        """Convert time windows from database format to model format."""
        result = {}
        try:
            for key, value in windows_dict.items():
                try:
                    channel = NotificationChannel(key)
                    window = NotificationTimeWindow(
                        start_time=datetime.strptime(value.get("start_time", "09:00"), "%H:%M").time(),
                        end_time=datetime.strptime(value.get("end_time", "21:00"), "%H:%M").time(),
                        timezone=value.get("timezone", "UTC")
                    )
                    result[channel] = window
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid time window format for {key}: {str(e)}")
                    # Use default value
                    result[NotificationChannel(key)] = NotificationTimeWindow()
        except Exception as e:
            logger.error(f"Error converting time windows: {str(e)}\n{traceback.format_exc()}")
            # Return default time windows
            return {
                NotificationChannel.IN_APP: NotificationTimeWindow(),
                NotificationChannel.EMAIL: NotificationTimeWindow()
            }
        return result

    async def get_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[NotificationResponse]:
        """Get notifications for a specific user."""
        try:
            # Build query
            query = select(Notification).where(Notification.user_id == user_id)

            # Add unread filter if requested
            if unread_only:
                query = query.where(Notification.read_at.is_(None))

            # Add ordering and pagination
            query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit)

            # Execute query
            result = await self.session.execute(query)
            notifications = result.scalars().all()

            # Convert to response models
            return [self._convert_to_response(n) for n in notifications]

        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to get notifications: {str(e)}")

    async def delete_notifications(
        self,
        notification_ids: List[UUID],
        user_id: UUID
    ) -> None:
        """Delete notifications by their IDs for a specific user."""
        try:
            # Delete notifications that belong to the user
            query = delete(Notification).where(
                and_(
                    Notification.id.in_(notification_ids),
                    Notification.user_id == user_id
                )
            )
            await self.session.execute(query)
            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting notifications: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to delete notifications: {str(e)}")

    async def get_user_preferences(self, user_id: UUID) -> UserPreferencesResponse:
        """Get user notification preferences."""
        try:
            # Try to get existing preferences
            query = select(UserPreferences).where(UserPreferences.user_id == user_id)
            result = await self.session.execute(query)
            preferences = result.scalar_one_or_none()

            if not preferences:
                # Create default preferences if none exist
                preferences = UserPreferences(
                    id=uuid4(),
                    user_id=user_id,
                    enabled_channels=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value],
                    notification_frequency={
                        "deal": {"type": "deal", "frequency": "immediate"},
                        "goal": {"type": "goal", "frequency": "immediate"},
                        "price_alert": {"type": "price_alert", "frequency": "immediate"},
                        "token": {"type": "token", "frequency": "daily"},
                        "security": {"type": "security", "frequency": "immediate"},
                        "market": {"type": "market", "frequency": "daily"},
                        "system": {"type": "system", "frequency": "immediate"}
                    },
                    time_windows={
                        "in_app": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"},
                        "email": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"}
                    },
                    theme=Theme.LIGHT.value,
                    language=Language.EN.value,
                    timezone="UTC",
                    do_not_disturb=False,
                    email_digest=True,
                    push_enabled=False,
                    sms_enabled=False,
                    telegram_enabled=False,
                    discord_enabled=False,
                    minimum_priority="low",
                    deal_alert_settings={},
                    price_alert_settings={},
                    email_preferences={}
                )
                self.session.add(preferences)
                await self.session.commit()
                await self.session.refresh(preferences)

            # Convert preferences to response model
            return UserPreferencesResponse(
                id=preferences.id,
                user_id=preferences.user_id,
                theme=Theme(preferences.theme),
                language=Language(preferences.language),
                timezone=preferences.timezone,
                enabled_channels=[NotificationChannel(ch) for ch in preferences.enabled_channels],
                notification_frequency=self._convert_notification_frequency(preferences.notification_frequency),
                time_windows=self._convert_time_windows(preferences.time_windows),
                muted_until=preferences.muted_until.time() if preferences.muted_until else None,
                do_not_disturb=preferences.do_not_disturb,
                email_digest=preferences.email_digest,
                push_enabled=preferences.push_enabled,
                sms_enabled=preferences.sms_enabled,
                telegram_enabled=preferences.telegram_enabled,
                discord_enabled=preferences.discord_enabled,
                minimum_priority=preferences.minimum_priority,
                deal_alert_settings=preferences.deal_alert_settings or {},
                price_alert_settings=preferences.price_alert_settings or {},
                email_preferences=preferences.email_preferences or {},
                created_at=preferences.created_at,
                updated_at=preferences.updated_at
            )

        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to get user preferences: {str(e)}")

    async def update_preferences(
        self,
        user_id: UUID,
        preferences_data: Dict[str, Any]
    ) -> UserPreferencesResponse:
        """Update user notification preferences."""
        try:
            # Get existing preferences or create new ones
            query = select(UserPreferences).where(UserPreferences.user_id == user_id)
            result = await self.session.execute(query)
            preferences = result.scalar_one_or_none()

            if not preferences:
                preferences = UserPreferences(user_id=user_id)
                self.session.add(preferences)

            # Update preferences with new data
            for key, value in preferences_data.items():
                if hasattr(preferences, key):
                    if key == "enabled_channels":
                        value = [ch.value for ch in value]
                    elif key == "notification_frequency":
                        value = {
                            k.value: {"type": k.value, "frequency": v.value}
                            for k, v in value.items()
                        }
                    elif key == "time_windows":
                        value = {
                            k.value: {
                                "start_time": v.start_time.strftime("%H:%M"),
                                "end_time": v.end_time.strftime("%H:%M"),
                                "timezone": v.timezone
                            }
                            for k, v in value.items()
                        }
                    setattr(preferences, key, value)

            await self.session.commit()
            await self.session.refresh(preferences)

            return await self.get_user_preferences(user_id)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating user preferences: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to update user preferences: {str(e)}")

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM,
        channels: List[NotificationChannel] = [NotificationChannel.IN_APP],
        notification_metadata: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        action_url: Optional[str] = None,
        schedule_for: Optional[datetime] = None,
        deal_id: Optional[UUID] = None,
        goal_id: Optional[UUID] = None,
        expires_at: Optional[datetime] = None
    ) -> NotificationResponse:
        """Create a new notification."""
        try:
            # Create notification record
            notification = Notification(
                id=uuid4(),
                user_id=user_id,
                goal_id=goal_id,
                deal_id=deal_id,
                title=title,
                message=message,
                type=notification_type.value,
                channels=[ch.value for ch in channels],
                priority=priority.value,
                notification_metadata=notification_metadata or {},
                action_url=action_url,
                status=NotificationStatus.PENDING.value,
                schedule_for=schedule_for,
                expires_at=expires_at,
                created_at=datetime.utcnow()
            )

            if self.session:
                self.session.add(notification)
                await self.session.commit()
                await self.session.refresh(notification)

            # Cache in Redis if enabled
            if self._redis_enabled:
                await self._cache_notification(notification)

            return self._convert_to_response(notification)

        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}\n{traceback.format_exc()}")
            if self.session:
                await self.session.rollback()
            raise NotificationError(f"Failed to create notification: {str(e)}")

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        if not self.session:
            raise NotificationError("Database session required for this operation")

        try:
            query = select(func.count()).select_from(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None)
                )
            )
            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to get unread count: {str(e)}")

    async def mark_as_read(
        self,
        notification_ids: List[UUID],
        user_id: UUID
    ) -> List[NotificationResponse]:
        """Mark notifications as read."""
        try:
            if not self.session:
                self.session = await get_async_db_session()

            # Get notifications that belong to the user
            notifications = await self.get_notifications_by_ids(notification_ids, user_id)
            if not notifications:
                return []

            # Update read_at timestamp
            now = datetime.utcnow()
            query = update(Notification).where(
                and_(
                    Notification.id.in_(notification_ids),
                    Notification.user_id == user_id
                )
            ).values(read_at=now)
            await self.session.execute(query)
            await self.session.commit()

            # Update cache if Redis is enabled
            if self._redis_enabled:
                for notification in notifications:
                    cache_key = f"notification:{notification.id}"
                    notification_dict = notification.dict()
                    notification_dict["read_at"] = now.isoformat()
                    await self._redis_client.set(
                        cache_key,
                        json.dumps(notification_dict),
                        expire=settings.NOTIFICATION_CACHE_TTL
                    )

            return notifications

        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to mark notifications as read: {str(e)}")

    async def clear_all_notifications(
        self,
        user_id: UUID
    ) -> None:
        """Clear all notifications for a specific user."""
        try:
            if not self.session:
                self.session = await get_async_db_session()

            # Delete all notifications for the user
            query = delete(Notification).where(Notification.user_id == user_id)
            await self.session.execute(query)
            await self.session.commit()

            # Clear cache if Redis is enabled
            if self._redis_enabled:
                # Get all notification keys for the user
                pattern = f"notification:*:{user_id}"
                keys = await self._redis_client.keys(pattern)
                if keys:
                    await self._redis_client.delete(*keys)

        except Exception as e:
            logger.error(f"Error clearing notifications: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to clear notifications: {str(e)}")

    async def _cache_notification(self, notification: Notification) -> None:
        """Cache notification in Redis."""
        if not self._redis_enabled:
            return

        try:
            key = f"notification:{notification.id}"
            value = self._convert_to_response(notification).model_dump()
            await self._redis_client.set(key, json.dumps(value), ex=3600)  # 1 hour TTL

        except Exception as e:
            logger.warning(f"Failed to cache notification: {str(e)}")

    async def get_notifications_by_ids(
        self,
        notification_ids: List[UUID],
        user_id: UUID
    ) -> List[NotificationResponse]:
        """Get notifications by their IDs for a specific user."""
        try:
            if not self.session:
                self.session = await get_async_db_session()

            query = select(Notification).where(
                and_(
                    Notification.id.in_(notification_ids),
                    Notification.user_id == user_id
                )
            )
            result = await self.session.execute(query)
            notifications = result.scalars().all()
            return [self._convert_to_response(n) for n in notifications]

        except Exception as e:
            logger.error(f"Error getting notifications by IDs: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to get notifications by IDs: {str(e)}")

    def set_background_tasks(self, background_tasks: BackgroundTasks) -> None:
        """Set background tasks for async operations."""
        self._background_tasks = background_tasks

    async def send_password_reset_email(
        self,
        email: str,
        reset_token: str,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> None:
        """Send password reset email."""
        try:
            reset_url = f"{settings.SITE_URL}/reset-password/{reset_token}"
            template_data = {
                "reset_url": reset_url,
                "site_name": settings.APP_NAME,
                "support_email": settings.EMAIL_FROM
            }
            
            # Render email template
            subject = "Password Reset Request"
            html_content = await render_template(
                "password_reset.html",
                template_data
            )
            text_content = await render_template(
                "password_reset.txt",
                template_data
            )
            
            # Send email
            if background_tasks:
                background_tasks.add_task(
                    email_service.send_email,
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content
                )
            else:
                await email_service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content
                )
                
        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to send password reset email: {str(e)}")

    async def send_magic_link_email(
        self,
        email: str,
        token: str,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> None:
        """Send magic link email."""
        try:
            magic_link_url = f"{settings.SITE_URL}/auth/verify-magic-link/{token}"
            template_data = {
                "magic_link_url": magic_link_url,
                "site_name": settings.APP_NAME,
                "support_email": settings.EMAIL_FROM
            }
            
            # Render email template
            subject = "Magic Link Login"
            html_content = await render_template(
                "magic_link.html",
                template_data
            )
            text_content = await render_template(
                "magic_link.txt",
                template_data
            )
            
            # Send email
            if background_tasks:
                background_tasks.add_task(
                    email_service.send_email,
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content
                )
            else:
                await email_service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content
                )
                
        except Exception as e:
            logger.error(f"Error sending magic link email: {str(e)}\n{traceback.format_exc()}")
            raise NotificationError(f"Failed to send magic link email: {str(e)}")
