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

# Disable SQLAlchemy logging
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy').propagate = False

# Configure async connection pooling with optimized settings
async_engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=False,  # Disable SQL logging
    echo_pool=False,  # Disable connection pool logging
    logging_name=None,  # Disable logging name
    pool_logging_name=None  # Disable pool logging name
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

@event.listens_for(async_engine.sync_engine, "connect")
def set_async_search_path(dbapi_connection, connection_record):
    """Set the search path and connection settings for async connections."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO public")
        cursor.execute("SET timezone TO 'UTC'")
        cursor.execute(f"SET idle_in_transaction_session_timeout TO '{settings.DB_IDLE_TIMEOUT * 1000}'")  # Convert to milliseconds
        cursor.close()
    except Exception as e:
        logger.error(f"Failed to set async database connection parameters: {str(e)}")
        raise

class AsyncDatabaseSession:
    """Async database session context manager."""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self) -> AsyncSession:
        self.session = AsyncSessionLocal()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        await self.session.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_async_db_session() -> AsyncSession:
    """Get async database session."""
    session = AsyncSessionLocal()
    try:
        return session
    except Exception as e:
        await session.close()
        raise e

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

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

__all__ = ['Base', 'async_engine', 'get_session']
