"""Connection monitoring utilities.

This module provides utilities for monitoring database connection pool usage and health.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.engine import Engine
import time

from core.database import async_engine, sync_engine
from core.metrics.database import DatabaseMetrics

logger = logging.getLogger(__name__)
metrics = DatabaseMetrics()

async def get_pool_status() -> Dict[str, Any]:
    """Get current database connection pool status.
    
    Returns:
        Dict[str, Any]: Information about the current connection pool status
    """
    # Get engine pool status
    async_pool = async_engine.pool
    sync_pool = sync_engine.pool
    
    # Get async pool stats
    async_stats = {}
    if async_pool:
        async_stats = {
            "size": async_pool.size(),
            "checkedin": async_pool.checkedin(),
            "checkedout": async_pool.checkedout(),
            "overflow": async_pool.overflow(),
            "timeout": getattr(async_engine, "pool_timeout", 60)  # Default to 60 if not found
        }
    
    # Get sync pool stats
    sync_stats = {}
    if sync_pool:
        sync_stats = {
            "size": sync_pool.size(),
            "checkedin": sync_pool.checkedin(),
            "checkedout": sync_pool.checkedout(),
            "overflow": sync_pool.overflow(),
        }
    
    return {
        "async_pool": async_stats,
        "sync_pool": sync_stats,
        "timestamp": time.time()
    }

async def log_pool_status() -> None:
    """Log current database connection pool status."""
    try:
        status = await get_pool_status()
        
        # Log async pool status
        async_pool = status["async_pool"]
        if async_pool:
            logger.info(
                f"Async pool status: size={async_pool.get('size', '?')}, "
                f"checkedin={async_pool.get('checkedin', '?')}, "
                f"checkedout={async_pool.get('checkedout', '?')}, "
                f"overflow={async_pool.get('overflow', '?')}"
            )
        
        # Log sync pool status
        sync_pool = status["sync_pool"]
        if sync_pool:
            logger.info(
                f"Sync pool status: size={sync_pool.get('size', '?')}, "
                f"checkedin={sync_pool.get('checkedin', '?')}, "
                f"checkedout={sync_pool.get('checkedout', '?')}, "
                f"overflow={sync_pool.get('overflow', '?')}"
            )
        
        # Update metrics
        if async_pool:
            metrics.update_pool_usage_metrics(
                async_pool.get('checkedout', 0),
                async_pool.get('overflow', 0),
                async_pool.get('size', 0),
            )
            
    except Exception as e:
        logger.error(f"Error getting pool status: {str(e)}")

async def monitor_connections(interval: int = 60) -> None:
    """Background task to monitor database connections.
    
    Args:
        interval (int): Monitoring interval in seconds
    """
    while True:
        try:
            await log_pool_status()
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Connection monitoring task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in connection monitoring: {str(e)}")
            await asyncio.sleep(interval)

async def detect_connection_leaks(
    timeout: int = 300, 
    threshold: int = 5,
    interval: int = 60
) -> None:
    """Background task to detect potential database connection leaks.
    
    This task checks if connections are being held open for too long
    and logs warnings accordingly.
    
    Args:
        timeout (int): How long a connection can remain checked out before triggering a warning (seconds)
        threshold (int): How many connections need to remain checked out to trigger the warning
        interval (int): How often to check for connection leaks (seconds)
    """
    while True:
        try:
            # Get initial connection status
            initial_status = await get_pool_status()
            initial_checkedout = initial_status["async_pool"].get("checkedout", 0)
            
            # Wait for the timeout period
            await asyncio.sleep(timeout)
            
            # Get current connection status
            current_status = await get_pool_status()
            current_checkedout = current_status["async_pool"].get("checkedout", 0)
            
            # If connections remain checked out for too long, log a warning
            if current_checkedout >= threshold and current_checkedout >= initial_checkedout:
                logger.warning(
                    f"Potential connection leak detected: {current_checkedout} connections "
                    f"remain checked out after {timeout} seconds"
                )
                
                # Force pool pre-ping to detect and reset stale connections
                logger.info("Triggering pool health check to detect stale connections")
                await async_engine.dispose()
                
            # Wait for the next check interval
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            logger.info("Connection leak detection task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in connection leak detection: {str(e)}")
            await asyncio.sleep(interval)

async def cleanup_connections() -> None:
    """Cleanup database connections by disposing the engines.
    
    This function can be called periodically to help mitigate connection issues.
    """
    try:
        logger.info("Cleaning up database connections")
        
        # Dispose async engine to close all connections
        await async_engine.dispose()
        
        # Dispose sync engine to close all connections
        sync_engine.dispose()
        
        logger.info("Database connections cleanup completed")
    except Exception as e:
        logger.error(f"Error cleaning up database connections: {str(e)}") 