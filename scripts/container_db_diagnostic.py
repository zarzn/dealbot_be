#!/usr/bin/env python
"""
Simple Database Connection Diagnostics for Docker Container

This script directly connects to the PostgreSQL database using environment variables
and checks the connection pool status to help diagnose connection issues.

Usage:
    docker exec CONTAINER_ID python /app/scripts/container_db_diagnostic.py
"""

import os
import sys
import time
import asyncio
import logging
from datetime import datetime
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db-diagnostics")

async def run_diagnostics(duration_seconds=60, interval_seconds=5):
    """Run connection diagnostics directly using SQLAlchemy."""
    try:
        # Import SQLAlchemy
        import sqlalchemy
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        
        logger.info(f"SQLAlchemy version: {sqlalchemy.__version__}")
        
        # Read database connection info from environment
        db_user = os.environ.get("POSTGRES_USER", "postgres")
        db_password = os.environ.get("POSTGRES_PASSWORD", "12345678")
        db_host = os.environ.get("POSTGRES_HOST", "deals_postgres")  # Container name in Docker network
        db_port = os.environ.get("POSTGRES_PORT", "5432")
        db_name = os.environ.get("POSTGRES_DB", "agentic_deals")
        
        # Build connection string
        db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        logger.info(f"Database URL: postgresql+asyncpg://{db_user}:***@{db_host}:{db_port}/{db_name}")
        
        # Create engine with pool settings
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=8,
            max_overflow=8,
            pool_timeout=15,
            pool_recycle=600,
            pool_pre_ping=True,
        )
        
        # Store samples
        samples = []
        start_time = datetime.now()
        logger.info(f"Starting connection monitoring for {duration_seconds}s with {interval_seconds}s intervals")
        
        # Take samples for the specified duration
        end_time = time.time() + duration_seconds
        while time.time() < end_time:
            # Check pool status
            pool = engine.pool
            stats = {
                "timestamp": datetime.now().isoformat(),
                "size": pool.size(),
                "checkedin": pool.checkedin(),
                "checkedout": pool.checkedout(),
                "overflow": pool.overflow(),
            }
            samples.append(stats)
            
            # Log current status
            logger.info(
                f"Pool status: size={stats['size']}, checked-in={stats['checkedin']}, "
                f"checked-out={stats['checkedout']}, overflow={stats['overflow']}"
            )
            
            # Execute a simple query to verify connection works
            try:
                async with AsyncSession(engine) as session:
                    result = await session.execute("SELECT 1 as test")
                    value = result.scalar()
                    logger.info(f"Test query result: {value}")
            except Exception as e:
                logger.error(f"Error executing test query: {str(e)}")
            
            # Wait before next sample
            await asyncio.sleep(interval_seconds)
        
        # Calculate metrics
        if samples:
            max_checkedout = max(s["checkedout"] for s in samples)
            avg_checkedout = sum(s["checkedout"] for s in samples) / len(samples)
            max_overflow = max(s["overflow"] for s in samples)
            
            logger.info("\n" + "="*50)
            logger.info("Connection Pool Analysis")
            logger.info(f"Duration: {(datetime.now() - start_time).total_seconds()} seconds")
            logger.info(f"Samples: {len(samples)}")
            logger.info(f"Max checked-out connections: {max_checkedout}")
            logger.info(f"Avg checked-out connections: {avg_checkedout:.1f}")
            logger.info(f"Max overflow: {max_overflow}")
            
            # Check for potential leak
            first_sample = samples[0]["checkedout"]
            last_sample = samples[-1]["checkedout"]
            if last_sample >= first_sample and last_sample > 4:  # 4 = 1/2 of default pool_size
                logger.warning("Potential connection leak detected!")
                logger.warning(f"Initial checked-out connections: {first_sample}")
                logger.warning(f"Final checked-out connections: {last_sample}")
            
            logger.info("="*50)
            
        # Dispose the engine
        await engine.dispose()
        logger.info("Diagnostics completed, engine disposed")
        
    except ImportError as e:
        logger.error(f"Import error: {str(e)}")
        logger.error("Make sure SQLAlchemy and asyncpg are installed")
    except Exception as e:
        logger.error(f"Error during diagnostics: {str(e)}")

async def main():
    """Script entry point"""
    logger.info("Container Database Diagnostics")
    logger.info(f"Python version: {sys.version}")
    
    try:
        # Get duration and interval from arguments or use defaults
        duration = 60
        interval = 5
        
        if len(sys.argv) > 1:
            try:
                duration = int(sys.argv[1])
            except ValueError:
                pass
        
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except ValueError:
                pass
                
        logger.info(f"Using duration: {duration}s, interval: {interval}s")
        
        # Run the diagnostics
        await run_diagnostics(duration, interval)
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 