"""Database initialization module.

This module handles the initialization of database tables and initial data setup.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging

from core.database import async_engine, Base

logger = logging.getLogger(__name__)

async def init_database() -> None:
    """Initialize database tables and verify connection."""
    try:
        # First verify connection
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection verified")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        raise 