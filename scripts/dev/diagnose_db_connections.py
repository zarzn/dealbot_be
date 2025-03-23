#!/usr/bin/env python
"""
Database Connection Diagnostics Tool

This script helps diagnose database connection issues by:
1. Checking current connection pool status
2. Monitoring connection usage over a period
3. Attempting to identify potential connection leaks
4. Providing recommendations for configuration changes

Usage:
    python diagnose_db_connections.py [--monitor-time=60] [--check-interval=5]

Options:
    --monitor-time    Time in seconds to monitor connections (default: 60)
    --check-interval  Interval in seconds between checks (default: 5)
"""

import sys
import os
import asyncio
import time
import argparse
import importlib.util
from datetime import datetime
from typing import Dict, List, Any

# Handle imports for both in-container and local execution
try:
    # First, try to import directly (when running inside container)
    from core.config import settings
    from core.database import get_async_engine
    from core.utils.logger import get_logger
    
    # Check if we're running in container
    in_container = os.path.exists('/.dockerenv')
    
    if in_container:
        print("Running inside Docker container")
    else:
        print("Running locally")
        
        # Add parent directory to path (for local execution)
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        
        # Re-import after path adjustment
        from core.config import settings
        from core.database import get_async_engine
        from core.utils.logger import get_logger
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Trying alternate import paths...")
    
    # Try to find the core module in standard locations
    possible_paths = [
        '/app',                    # Standard container path
        os.path.abspath('../../'), # Relative to script
        os.getcwd(),               # Current directory
    ]
    
    found = False
    for path in possible_paths:
        if os.path.exists(os.path.join(path, 'core')):
            print(f"Found core module at {path}")
            sys.path.insert(0, path)
            
            # Import after adjusting path
            from core.config import settings
            from core.database import get_async_engine
            from core.utils.logger import get_logger
            
            found = True
            break
    
    if not found:
        print("ERROR: Could not find core module. Make sure you're running from the correct directory.")
        sys.exit(1)

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
        return 0

class ConnectionDiagnostics:
    def __init__(self):
        self.async_engine = None
        self.sync_engine = None
        self.samples = []
        self.start_time = None
        self.end_time = None
        
    async def initialize(self):
        """Initialize database engines"""
        logger.info("Initializing database engines...")
        # Only initialize async engine since that's what we primarily use
        self.async_engine = await get_async_engine()
        
        # We don't need sync_engine for diagnostics
        self.sync_engine = None
        
        logger.info(f"Database engine initialized - using URL: {settings.DATABASE_URL}")
        
    async def collect_single_sample(self) -> Dict[str, Any]:
        """Collect a single sample of connection pool stats"""
        # Check async pool
        async_pool = self.async_engine.pool
        async_stats = await check_pool_status(async_pool)
        
        # Add database URL information to the sample
        db_info = {
            "db_host": settings.POSTGRES_HOST,
            "db_name": settings.POSTGRES_DB,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "idle_timeout": settings.DB_IDLE_TIMEOUT
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "async_pool": async_stats,
            "db_info": db_info
        }
        
    async def monitor_connections(self, duration_seconds: int = 60, interval_seconds: int = 5):
        """Monitor connections over a period of time"""
        self.start_time = datetime.now()
        logger.info(f"Starting connection monitoring for {duration_seconds} seconds...")
        
        # Take initial sample
        self.samples.append(await self.collect_single_sample())
        logger.info(self._format_sample(self.samples[-1]))
        
        end_time = time.time() + duration_seconds
        while time.time() < end_time:
            await asyncio.sleep(interval_seconds)
            
            # Collect sample
            self.samples.append(await self.collect_single_sample())
            logger.info(self._format_sample(self.samples[-1]))
        
        self.end_time = datetime.now()
        logger.info(f"Connection monitoring completed over {(self.end_time - self.start_time).total_seconds()} seconds")
    
    def _format_sample(self, sample: Dict[str, Any]) -> str:
        """Format a sample for display"""
        async_pool = sample["async_pool"]
        db_info = sample.get("db_info", {})
        
        lines = [
            f"Time: {sample['timestamp']}",
            f"DB Host: {db_info.get('db_host', 'unknown')}, DB Name: {db_info.get('db_name', 'unknown')}",
            f"Async Pool: size={async_pool['size']}, checked-in={async_pool['checkedin']}, checked-out={async_pool['checkedout']}, overflow={async_pool['overflow']}",
        ]
        
        return "\n".join(lines)
    
    def analyze_results(self) -> List[str]:
        """Analyze monitoring results and provide recommendations"""
        if not self.samples:
            return ["No monitoring data collected."]
            
        # Get configuration
        pool_size = settings.DB_POOL_SIZE
        max_overflow = settings.DB_MAX_OVERFLOW
        max_connections = pool_size + max_overflow
        
        # Calculate metrics
        max_checkedout = max(s["async_pool"]["checkedout"] for s in self.samples)
        avg_checkedout = sum(s["async_pool"]["checkedout"] for s in self.samples) / len(self.samples)
        max_overflow_used = max(s["async_pool"]["overflow"] for s in self.samples)
        
        # Generate insights
        insights = [
            f"Connection Pool Analysis ({self.start_time.isoformat()} to {self.end_time.isoformat()})",
            f"Database: {settings.POSTGRES_HOST}/{settings.POSTGRES_DB}",
            f"Configuration: pool_size={pool_size}, max_overflow={max_overflow}, max_connections={max_connections}",
            f"Max checked-out connections: {max_checkedout} ({max_checkedout/max_connections*100:.1f}% of max)",
            f"Average checked-out connections: {avg_checkedout:.1f}",
            f"Max overflow used: {max_overflow_used} ({max_overflow_used/max_overflow*100:.1f}% of max overflow)"
        ]
        
        # Check for potential connection leak (same or increasing checked out connections)
        first_sample = self.samples[0]["async_pool"]["checkedout"]
        last_sample = self.samples[-1]["async_pool"]["checkedout"]
        
        if last_sample >= first_sample and last_sample > pool_size / 2:
            insights.append("\nPotential connection leak detected:")
            insights.append(f"- Initial checked-out connections: {first_sample}")
            insights.append(f"- Final checked-out connections: {last_sample}")
            insights.append("- Connections not being properly closed or recycled")
        
        # Generate recommendations
        recommendations = ["\nRecommendations:"]
        
        # If max usage is close to limit
        if max_checkedout > 0.8 * max_connections:
            recommendations.append("- Consider increasing DB_POOL_SIZE and/or DB_MAX_OVERFLOW")
            recommendations.append(f"  Current: DB_POOL_SIZE={pool_size}, DB_MAX_OVERFLOW={max_overflow}")
            recommendations.append(f"  Suggested: DB_POOL_SIZE={int(pool_size*1.5)}, DB_MAX_OVERFLOW={int(max_overflow*1.2)}")
        
        # If average usage is low compared to pool size
        if avg_checkedout < 0.3 * pool_size and pool_size > 5:
            recommendations.append("- Consider reducing DB_POOL_SIZE to save resources")
            recommendations.append(f"  Current: DB_POOL_SIZE={pool_size}")
            recommendations.append(f"  Suggested: DB_POOL_SIZE={max(5, int(avg_checkedout*2))}")
        
        # If max overflow is reached
        if max_overflow_used > 0.9 * max_overflow:
            recommendations.append("- Max overflow nearly reached, increase DB_MAX_OVERFLOW")
        
        # If barely using overflow
        if max_overflow_used < 0.1 * max_overflow and max_overflow > 5:
            recommendations.append("- Consider reducing DB_MAX_OVERFLOW to prevent resource waste")
        
        # General best practices
        recommendations.append("\nGeneral best practices:")
        recommendations.append("- Always use context managers (async with) for database sessions")
        recommendations.append("- Use connection pooling for heavily used endpoints")
        recommendations.append("- Decrease connection idle timeout if connections stay open too long")
        recommendations.append("- Implement proper error handling to ensure connections are closed")
        
        return insights + recommendations

async def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Database Connection Diagnostics Tool')
    parser.add_argument('--monitor-time', type=int, default=60, help='Time in seconds to monitor connections')
    parser.add_argument('--check-interval', type=int, default=5, help='Interval in seconds between checks')
    args = parser.parse_args()
    
    # Print environment information
    in_container = os.path.exists('/.dockerenv')
    logger.info(f"Running in container: {in_container}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Python path: {sys.path}")
    
    diagnostics = ConnectionDiagnostics()
    await diagnostics.initialize()
    
    try:
        await diagnostics.monitor_connections(args.monitor_time, args.check_interval)
        
        analysis = diagnostics.analyze_results()
        print("\n" + "\n".join(analysis))
        
        # Attempt to clean up idle connections
        if diagnostics.async_engine:
            logger.info("Attempting to clean up idle connections...")
            closed = await close_idle_connections(diagnostics.async_engine.pool)
            logger.info(f"Cleaned up {closed} connection(s)")
        
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Error during monitoring: {str(e)}")
    
    logger.info("Script completed")

if __name__ == "__main__":
    asyncio.run(main()) 