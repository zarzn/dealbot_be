"""Database configuration and session management.

This module provides database connection setup, session management, and connection pooling
for the AI Agentic Deals System.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import event, text
from typing import AsyncGenerator, Optional
import asyncio
import logging
from contextlib import asynccontextmanager

from core.config import settings

logger = logging.getLogger(__name__)

# Configure connection pooling with optimized settings
engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Configure session factory with transaction management
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions with monitoring."""
    session: Optional[AsyncSession] = None
    
    try:
        session = async_session()
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        if session:
            await session.rollback()
        logger.error(f"Database transaction failed: {str(e)}")
        raise
    finally:
        if session:
            await session.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session with retry logic."""
    max_retries = settings.DB_MAX_RETRIES
    retry_delay = settings.DB_RETRY_DELAY
    
    for attempt in range(max_retries):
        try:
            async with get_db_session() as session:
                yield session
                break
        except OperationalError as e:
            if attempt == max_retries - 1:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2 