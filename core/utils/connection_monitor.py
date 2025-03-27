"""
Connection monitoring utilities for database and Redis pools.

This module provides utilities to monitor connection pools, detect leaks,
and automatically clean up idle connections to prevent resource exhaustion.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine
from redis.asyncio import Redis

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def check_pool_status(db_pool) -> Dict[str, Any]:
    """Check the status of a SQLAlchemy connection pool.
    
    Args:
        db_pool: The SQLAlchemy pool object to check
        
    Returns:
        Dictionary with pool statistics
    """
    stats = {
        "size": db_pool.size(),
        "checkedin": db_pool.checkedin(),
        "checkedout": db_pool.checkedout(),
        "overflow": db_pool.overflow()
    }
    
    return stats

async def close_idle_connections(db_pool, idle_seconds: int = 300) -> int:
    """Close connections that have been idle for more than the specified time.
    
    Args:
        db_pool: The SQLAlchemy pool object
        idle_seconds: Number of seconds a connection can be idle before closing
        
    Returns:
        Number of connections closed
    """
    # This is a simplified approach - in practice, SQLAlchemy's pool manages
    # this internally based on pool_recycle and pool_timeout settings
    logger.info("Cleaning up database connections")
    
    try:
        # For SQLAlchemy 2.0, we can use db_pool.dispose() to close all connections
        # and let the pool recreate them as needed
        await db_pool.dispose()
        logger.info("Database connections cleanup completed")
        return 1
    except Exception as e:
        logger.error(f"Error cleaning up database connections: {str(e)}")
        # If we get a MissingGreenlet error, it means we're trying to close connections
        # from a non-async context or outside the expected async context
        if 'MissingGreenlet' in str(e):
            logger.warning("MissingGreenlet error detected - attempting safer cleanup approach")
            try:
                # Schedule the cleanup to run in a proper async context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        safe_dispose_pool(db_pool), loop
                    )
                    future.result(timeout=5)  # Wait up to 5 seconds for completion
                    return 1
            except Exception as inner_e:
                logger.error(f"Failed even with safer cleanup approach: {str(inner_e)}")
        return 0

async def safe_dispose_pool(db_pool):
    """A safer version of pool disposal that handles exceptions more gracefully.
    
    Args:
        db_pool: The SQLAlchemy pool object to dispose
    """
    try:
        # Set the pool's pre_ping to False to avoid unnecessary checks during cleanup
        db_pool._pre_ping = False
        
        # Close connections one by one instead of all at once
        size = db_pool.size()
        for _ in range(size):
            try:
                conn = await db_pool.connect()
                await conn.close()
            except Exception as e:
                logger.warning(f"Error closing individual connection: {str(e)}")
        
        logger.info("Completed safer connection pool cleanup")
    except Exception as e:
        logger.error(f"Error in safe_dispose_pool: {str(e)}")

async def monitor_database_connections(interval: int = 60):
    """Continuously monitor database connections and log statistics.
    
    Args:
        interval: Check interval in seconds
    """
    from core.database import async_engine, sync_engine, get_async_db_context
    
    logger.info("Starting database connection monitoring...")
    
    # Get the engine instances directly
    async_engine_instance = async_engine
    sync_engine_instance = sync_engine
    
    while True:
        try:
            # Check async pool status
            async_pool = async_engine_instance.pool
            async_stats = await check_pool_status(async_pool)
            logger.info(f"Async pool status: size={async_stats['size']}, checkedin={async_stats['checkedin']}, checkedout={async_stats['checkedout']}, overflow={async_stats['overflow']}")
            
            # Check sync pool status if available
            if hasattr(sync_engine_instance, 'pool'):
                sync_pool = sync_engine_instance.pool
                sync_stats = {
                    "size": sync_pool.size(),
                    "checkedin": sync_pool.checkedin(),
                    "checkedout": sync_pool.checkedout(),
                    "overflow": sync_pool.overflow()
                }
                logger.info(f"Sync pool status: size={sync_stats['size']}, checkedin={sync_stats['checkedin']}, checkedout={sync_stats['checkedout']}, overflow={sync_stats['overflow']}")
            
            # If we detect a high utilization (>80% of max connections)
            max_connections = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
            if async_stats['checkedout'] > max_connections * 0.8:
                logger.warning(f"High database connection utilization: {async_stats['checkedout']}/{max_connections} connections in use")
                
                # Clean up idle connections
                await close_idle_connections(async_pool)
                
                # If we're still at high utilization, try to recover by disposing the pool
                if async_stats['checkedout'] > max_connections * 0.9:
                    logger.warning("Critical database connection utilization, disposing pool")
                    
                    # Use our improved context manager to ensure we're in a proper async context
                    try:
                        await safe_dispose_pool(async_pool)
                    except Exception as pool_e:
                        logger.error(f"Error in controlled pool disposal: {str(pool_e)}")
                        
                    # As a last resort, try normal disposal with error handling
                    try:
                        await async_engine_instance.dispose()
                        logger.info("Pool disposed and will be recreated on next access")
                    except Exception as e:
                        logger.error(f"Error disposing pool: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error monitoring database connections: {str(e)}")
        
        # Wait for the next check interval
        await asyncio.sleep(interval)

def start_connection_monitor():
    """Start the connection monitoring as a background task."""
    asyncio.create_task(monitor_database_connections())
    logger.info("Database connection monitoring started") 