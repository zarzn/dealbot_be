"""Database configuration and session management.

This module provides database connection setup, session management, and connection pooling
for the AI Agentic Deals System. It includes retry logic and monitoring capabilities.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import event, text
from typing import AsyncGenerator, Generator, Optional
import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager

from core.config import settings
from core.metrics.database import DatabaseMetrics

logger = logging.getLogger(__name__)
metrics = DatabaseMetrics()

# Configure async connection pooling with optimized settings
async_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True
)

# Configure sync engine
sync_engine = create_engine(
    str(settings.sync_database_url),
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Configure session factories with transaction management
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)

SessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    class_=Session
)

# Create base class for models
Base = declarative_base()

# Add connection event listeners
@event.listens_for(sync_engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """Set the search path and connection settings."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO public")
        cursor.execute("SET timezone TO 'UTC'")
        cursor.execute(f"SET idle_in_transaction_session_timeout TO '{settings.DB_IDLE_TIMEOUT * 1000}'")  # Convert to milliseconds
        cursor.close()
    except Exception as e:
        logger.error(f"Failed to set database connection parameters: {str(e)}")
        raise

@event.listens_for(sync_engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Monitor connection checkouts for metrics."""
    metrics.connection_checkouts.inc()

@event.listens_for(sync_engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Monitor connection checkins for metrics."""
    metrics.connection_checkins.inc()

@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for async database sessions with monitoring."""
    session: Optional[AsyncSession] = None
    start_time = time.time()
    
    try:
        session = AsyncSessionLocal()
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        if session:
            await session.rollback()
        metrics.connection_failures.inc()
        logger.error(f"Database transaction failed: {str(e)}")
        raise
    finally:
        if session:
            await session.close()

@contextmanager
def get_sync_db_session() -> Generator[Session, None, None]:
    """Context manager for sync database sessions with monitoring."""
    session: Optional[Session] = None
    start_time = time.time()
    
    try:
        session = SessionLocal()
        yield session
        session.commit()
    except SQLAlchemyError as e:
        if session:
            session.rollback()
        metrics.connection_failures.inc()
        logger.error(f"Database transaction failed: {str(e)}")
        raise
    finally:
        if session:
            session.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session with retry logic."""
    max_retries = settings.DB_MAX_RETRIES
    retry_delay = settings.DB_RETRY_DELAY
    
    for attempt in range(max_retries):
        try:
            async with get_async_db_session() as session:
                yield session
                break
        except OperationalError as e:
            if attempt == max_retries - 1:
                metrics.connection_failures.inc()
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2

def get_sync_db() -> Generator[Session, None, None]:
    """Dependency that provides a sync database session with retry logic."""
    max_retries = settings.DB_MAX_RETRIES
    retry_delay = settings.DB_RETRY_DELAY
    
    for attempt in range(max_retries):
        try:
            with get_sync_db_session() as session:
                yield session
                break
        except OperationalError as e:
            if attempt == max_retries - 1:
                metrics.connection_failures.inc()
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2

async def init_db() -> None:
    """Initialize database tables and verify connection."""
    try:
        async with async_engine.begin() as conn:
            # Verify connection
            await conn.execute(text("SELECT 1"))
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

async def check_db_connection() -> bool:
    """Check database connection health."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

__all__ = [
    'async_engine',
    'sync_engine',
    'AsyncSessionLocal',
    'SessionLocal',
    'get_db',
    'get_sync_db',
    'get_async_db_session',
    'get_sync_db_session',
    'Base',
    'init_db'
] 