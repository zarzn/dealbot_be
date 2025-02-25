"""Notification processing tasks."""

from typing import List, Dict, Any, Optional, NoReturn
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
import logging
from enum import Enum

from core.config import get_settings
from core.models.database import Notification
from core.services.notification_service import NotificationService
from core.services.redis import get_redis_service
from core.utils.logger import get_logger
from core.exceptions.base_exceptions import BaseError
from core.celery import celery_app

class NotificationType(str, Enum):
    """Notification type enum."""
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    IN_APP = "in_app"

logger = logging.getLogger(__name__)

# Create synchronous engine and session factory
settings = get_settings()
engine = create_engine(str(settings.sync_database_url))
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Session:
    """Get synchronous database session."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

@celery_app.task(
    name="process_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="100/m"
)
def process_notifications(self) -> Dict[str, Any]:
    """Process pending notifications"""
    db = get_db()
    try:
        # Get pending notifications
        notifications = db.query(Notification).filter(
            Notification.sent_at.is_(None),
            Notification.error.is_(None)
        ).order_by(
            Notification.priority.desc(),
            Notification.created_at.asc()
        ).limit(100).all()

        if not notifications:
            return {
                "status": "success",
                "message": "No pending notifications found",
                "processed": 0
            }

        notification_service = NotificationService()
        processed = 0
        errors = 0

        # Process notifications by type
        for notification in notifications:
            try:
                if notification.type == NotificationType.EMAIL:
                    notification_service.send_email_notification(notification)
                elif notification.type == NotificationType.PUSH:
                    notification_service.send_push_notification(notification)
                elif notification.type == NotificationType.SMS:
                    notification_service.send_sms_notification(notification)

                notification.sent_at = datetime.utcnow()
                processed += 1

            except Exception as e:
                logger.error(f"Error processing notification {notification.id}: {str(e)}")
                notification.error = str(e)
                errors += 1

        db.commit()

        return {
            "status": "success",
            "message": "Notifications processed successfully",
            "processed": processed,
            "errors": errors,
            "total": len(notifications)
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error in notification processing task: {str(e)}")
        self.retry(exc=e)
    finally:
        db.close()

@celery_app.task(
    name="cleanup_old_notifications",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def cleanup_old_notifications(self, days: int = 30) -> Dict[str, Any]:
    """Clean up old notifications"""
    db = get_db()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get old notifications
        notifications = db.query(Notification).filter(
            Notification.created_at < cutoff_date
        ).all()

        if not notifications:
            return {
                "status": "success",
                "message": "No old notifications to clean up",
                "deleted": 0
            }

        # Delete from database
        for notification in notifications:
            db.delete(notification)

        db.commit()

        try:
            # Clean up Redis cache
            redis = get_redis_service()
            for notification in notifications:
                redis.delete(f"notification:{notification.id}")
                # Remove from user's notification list
                user_key = f"user:{notification.user_id}:notifications"
                redis.lrem(user_key, 0, notification.id)
        except Exception as e:
            logger.error(f"Redis cleanup error: {str(e)}")
            # Continue since DB cleanup was successful

        return {
            "status": "success",
            "message": "Old notifications cleaned up successfully",
            "deleted": len(notifications)
        }

    except (BaseError, Exception) as e:
        db.rollback()
        logger.error(f"Error in notification cleanup task: {str(e)}")
        self.retry(exc=e)
    finally:
        db.close()

@celery_app.task(
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
    db = get_db()
    try:
        notification_service = NotificationService()
        successful = 0
        failed = 0
        errors = []

        for user_id in user_ids:
            try:
                notification_service.send_notification(
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
        self.retry(exc=e)
    finally:
        db.close()
