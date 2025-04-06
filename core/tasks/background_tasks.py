import asyncio
import logging
from core.database import cleanup_idle_connections
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import shared_task
from sqlalchemy import select

from core.database import get_session
from core.models.shared_content import SharedContent
from core.services.sharing import SharingService
from core.utils.metrics import track_metric
from core.exceptions import ServiceError as ServiceException
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def periodic_database_cleanup():
    """
    Periodically clean up idle database connections to prevent connection pool exhaustion.
    
    This task runs every 2 minutes to identify and close idle database connections.
    It's critical for preventing RDS connection slot exhaustion.
    """
    # Initial cleanup delay after application start
    initial_delay = 30  # Run first cleanup 30 seconds after startup
    
    # Set how frequently to run cleanup
    cleanup_interval = 120  # Run every 2 minutes (reduced from 5 minutes)
    
    # Add jitter to avoid all instances running cleanup at the same time
    import random
    jitter = random.randint(0, 15)  # 0-15 seconds of jitter
    
    # Wait for initial startup delay with jitter
    await asyncio.sleep(initial_delay + jitter)
    
    while True:
        try:
            logger.info("Starting periodic database connection cleanup")
            
            # Run the cleanup and log results
            connections_cleaned = await cleanup_idle_connections()
            
            if connections_cleaned > 0:
                logger.info(f"Cleaned up {connections_cleaned} idle database connections")
            else:
                logger.debug("No idle database connections to clean up")
            
            # Check database pool status for high utilization
            try:
                from core.database import async_engine
                from core.config import settings
                
                # Check pool status
                async_pool = async_engine.pool
                size = async_pool.size()
                checkedout = async_pool.checkedout()
                checkedin = async_pool.checkedin()
                overflow = async_pool.overflow()
                
                logger.info(f"DB Pool status: size={size}, checkedout={checkedout}, checkedin={checkedin}, overflow={overflow}")
                
                # If utilization is high, run cleanup more aggressively
                max_connections = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
                if checkedout > max_connections * 0.7:
                    logger.warning(f"High DB connection utilization: {checkedout}/{max_connections}")
                    
                    # If very high utilization, try more aggressive measures
                    if checkedout > max_connections * 0.9:
                        logger.critical(f"CRITICAL DB connection utilization: {checkedout}/{max_connections}")
                        
                        # Try to recycle the pool
                        try:
                            from core.utils.connection_monitor import safe_dispose_pool
                            logger.warning("Attempting to safely dispose connection pool due to high utilization")
                            await safe_dispose_pool(async_pool)
                            logger.info("Successfully disposed connection pool")
                        except Exception as pool_e:
                            logger.error(f"Failed to dispose pool: {str(pool_e)}")
            except Exception as status_e:
                logger.error(f"Error checking pool status: {str(status_e)}")
            
            # Wait before next cleanup
            await asyncio.sleep(cleanup_interval)
            
        except Exception as e:
            logger.error(f"Error in periodic database cleanup task: {str(e)}")
            # Still wait before retry even if there was an error
            await asyncio.sleep(cleanup_interval)

@shared_task(
    bind=True,
    queue='cleanup',
    rate_limit='10/h'
)
async def cleanup_expired_shared_content(self) -> Dict[str, Any]:
    """Task to clean up expired shared content from the database.
    
    This task finds all shared content that has passed its expiration date
    and removes it from the database to maintain database health and privacy.
    
    Returns:
        Dict containing task execution statistics
    """
    start_time = datetime.utcnow()
    stats = {
        'content_cleaned': 0,
        'errors': 0
    }
    
    try:
        logger.info("Starting shared content cleanup task")
        track_metric("shared_content_cleanup_started")
        
        async for db in get_session():
            # Get expired shared content
            query = select(SharedContent).where(
                (SharedContent.expires_at < datetime.utcnow()) & 
                (SharedContent.is_active == True)
            )
            result = await db.execute(query)
            expired_contents = result.scalars().all()
            
            logger.info(f"Found {len(expired_contents)} expired shared content items")
            
            # Create sharing service
            sharing_service = SharingService(db)
            
            # Process each expired content
            for content in expired_contents:
                try:
                    # Deactivate the content (we don't delete to maintain auditing)
                    content.is_active = False
                    
                    # Add a note that it was automatically expired
                    if not content.description:
                        content.description = "Automatically expired by system cleanup"
                    else:
                        content.description += " (Automatically expired by system cleanup)"
                    
                    # Update the database
                    await db.commit()
                    
                    stats['content_cleaned'] += 1
                    
                except Exception as e:
                    logger.error(
                        f"Error cleaning up shared content {content.share_id}: {str(e)}",
                        exc_info=True
                    )
                    stats['errors'] += 1
                    await db.rollback()
                    continue
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        stats['execution_time'] = execution_time
        
        logger.info(
            "Completed shared content cleanup task",
            extra={'stats': stats}
        )
        track_metric("shared_content_cleanup_completed", stats['content_cleaned'])
        
        return stats
        
    except Exception as e:
        logger.error(f"Shared content cleanup task failed: {str(e)}", exc_info=True)
        stats['errors'] += 1
        return stats 

@shared_task(
    bind=True,
    acks_late=True,
    name="cleanup.remove_expired_shares",
    queue="cleanup",
    max_retries=3,
    default_retry_delay=60,
)
async def cleanup_expired_shares(self) -> dict:
    """
    Background task to clean up expired shared links from the database.
    This prevents accumulation of unnecessary data and improves database performance.
    
    Returns:
        dict: Information about the cleanup operation, including the number of shares removed
    """
    logger.info("Starting cleanup of expired shared links")
    try:
        sharing_service = SharingService()
        result = await sharing_service.delete_expired_shares()
        logger.info(f"Successfully removed {result['removed_count']} expired shared links")
        return {
            "status": "success",
            "removed_count": result["removed_count"],
            "message": f"Successfully removed {result['removed_count']} expired shared links"
        }
    except ServiceException as e:
        logger.error(f"Error in cleanup_expired_shares task: {str(e)}")
        self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error in cleanup_expired_shares task: {str(e)}")
        self.retry(exc=e)
        
    return {
        "status": "error",
        "removed_count": 0,
        "message": "Failed to clean up expired shared links"
    } 