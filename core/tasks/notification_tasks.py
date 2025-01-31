from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from celery import shared_task
from sqlalchemy import select

from ..database import async_session_factory
from ..models.notification import Notification, NotificationType
from ..services.notification import NotificationService
from ..utils.redis import get_redis_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

@shared_task(
    name="process_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="100/m"
)
def process_notifications(self) -> Dict[str, Any]:
    """Process pending notifications"""
    try:
        # Run async task
        return asyncio.run(_process_notifications_async())
    except Exception as e:
        logger.error(f"Error processing notifications: {str(e)}")
        self.retry(exc=e)

async def _process_notifications_async() -> Dict[str, Any]:
    """Async implementation of notification processing"""
    async with async_session_factory() as session:
        try:
            # Get pending notifications
            result = await session.execute(
                select(Notification).where(
                    Notification.sent_at.is_(None),
                    Notification.error.is_(None)
                ).order_by(
                    Notification.priority.desc(),
                    Notification.created_at.asc()
                ).limit(100)
            )
            notifications = list(result.scalars().all())

            if not notifications:
                return {
                    "status": "success",
                    "message": "No pending notifications found",
                    "processed": 0
                }

            notification_service = NotificationService(session)
            processed = 0
            errors = 0

            # Process notifications by type
            for notification in notifications:
                try:
                    if notification.type == NotificationType.EMAIL:
                        await notification_service._send_email_notification(notification)
                    elif notification.type == NotificationType.PUSH:
                        await notification_service._send_push_notification(notification)
                    elif notification.type == NotificationType.SMS:
                        await notification_service._send_sms_notification(notification)

                    notification.sent_at = datetime.utcnow()
                    processed += 1

                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {str(e)}")
                    notification.error = str(e)
                    errors += 1

            await session.commit()

            return {
                "status": "success",
                "message": "Notifications processed successfully",
                "processed": processed,
                "errors": errors,
                "total": len(notifications)
            }

        except Exception as e:
            await session.rollback()
            logger.error(f"Error in notification processing task: {str(e)}")
            raise

@shared_task(
    name="cleanup_old_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def cleanup_old_notifications(self, days: int = 30) -> Dict[str, Any]:
    """Clean up old notifications"""
    try:
        # Run async task
        return asyncio.run(_cleanup_old_notifications_async(days))
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}")
        self.retry(exc=e)

async def _cleanup_old_notifications_async(days: int) -> Dict[str, Any]:
    """Async implementation of notification cleanup"""
    async with async_session_factory() as session:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get old notifications
            result = await session.execute(
                select(Notification).where(
                    Notification.created_at < cutoff_date
                )
            )
            notifications = list(result.scalars().all())

            if not notifications:
                return {
                    "status": "success",
                    "message": "No old notifications to clean up",
                    "deleted": 0
                }

            # Delete from database
            for notification in notifications:
                await session.delete(notification)

            await session.commit()

            # Clean up Redis cache
            redis = await get_redis_client()
            for notification in notifications:
                await redis.delete(f"notification:{notification.id}")
                # Remove from user's notification list
                user_key = f"user:{notification.user_id}:notifications"
                await redis.lrem(user_key, 0, notification.id)

            return {
                "status": "success",
                "message": "Old notifications cleaned up successfully",
                "deleted": len(notifications)
            }

        except Exception as e:
            await session.rollback()
            logger.error(f"Error in notification cleanup task: {str(e)}")
            raise

@shared_task(
    name="send_batch_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="10/m"
)
def send_batch_notifications(
    self,
    user_ids: List[str],
    title: str,
    message: str,
    notification_type: str = NotificationType.IN_APP.value,
    data: Optional[Dict[str, Any]] = None,
    priority: bool = False
) -> Dict[str, Any]:
    """Send notifications to multiple users"""
    try:
        # Run async task
        return asyncio.run(_send_batch_notifications_async(
            user_ids=user_ids,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data,
            priority=priority
        ))
    except Exception as e:
        logger.error(f"Error sending batch notifications: {str(e)}")
        self.retry(exc=e)

async def _send_batch_notifications_async(
    user_ids: List[str],
    title: str,
    message: str,
    notification_type: str,
    data: Optional[Dict[str, Any]] = None,
    priority: bool = False
) -> Dict[str, Any]:
    """Async implementation of batch notification sending"""
    async with async_session_factory() as session:
        try:
            notification_service = NotificationService(session)
            successful = 0
            failed = 0
            errors = []

            for user_id in user_ids:
                try:
                    await notification_service.send_notification(
                        user_id=user_id,
                        title=title,
                        message=message,
                        notification_type=NotificationType(notification_type),
                        data=data,
                        priority=priority
                    )
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append({
                        "user_id": user_id,
                        "error": str(e)
                    })
                    logger.error(f"Error sending notification to user {user_id}: {str(e)}")

            return {
                "status": "success",
                "message": "Batch notifications processed",
                "successful": successful,
                "failed": failed,
                "total": len(user_ids),
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Error in batch notification task: {str(e)}")
            raise 