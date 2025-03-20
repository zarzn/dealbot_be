"""Tasks for handling announcements."""

from celery import shared_task
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from core.db.session import get_async_session
from core.utils.logger import get_logger
from core.services.announcement import AnnouncementService

logger = get_logger(__name__)


@shared_task(name="check_scheduled_announcements")
async def check_scheduled_announcements() -> None:
    """Check for scheduled announcements that should be published.
    
    This task runs periodically (e.g., every 15 minutes) to check for
    scheduled announcements that have reached their publish date and
    should be published. It also handles archiving expired announcements.
    """
    logger.info("Running scheduled announcements check task")
    
    try:
        # Get database session
        async for db in get_async_session():
            announcement_service = AnnouncementService(db)
            
            # Publish scheduled announcements
            published_count = await announcement_service.check_scheduled_announcements()
            if published_count > 0:
                logger.info(f"Published {published_count} scheduled announcements")
            
            # Archive expired announcements
            archived_count = await announcement_service.archive_expired_announcements()
            if archived_count > 0:
                logger.info(f"Archived {archived_count} expired announcements")
                
    except Exception as e:
        logger.error(f"Error in scheduled announcements check task: {str(e)}") 