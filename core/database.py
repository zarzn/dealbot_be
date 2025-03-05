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
from typing import AsyncGenerator, Generator, Optional, Dict, Any
import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager
import os

from core.config import settings
from core.metrics.database import DatabaseMetrics

logger = logging.getLogger(__name__)
metrics = DatabaseMetrics()

# Disable SQLAlchemy logging
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy').propagate = False

# Determine environment-specific pool settings
# Convert FieldInfo to string to avoid linter errors
environment = str(settings.APP_ENVIRONMENT).lower()
is_production = environment == "production"
is_test = environment == "test"

# Performance Optimizations for Database
# Constants for query optimization
DB_STATEMENT_TIMEOUT_SECONDS = 60 if is_production else 30
DB_SLOW_QUERY_LOG_SECONDS = 1.0  # Log queries that take more than 1 second

# Optimize pool settings based on environment
if is_production:
    # Production pool settings - larger pool, longer recycle time
    pool_size = settings.DB_POOL_SIZE * 2  # Double pool size for production
    max_overflow = settings.DB_MAX_OVERFLOW * 2  # Double max overflow for production
    pool_timeout = settings.DB_POOL_TIMEOUT  # Keep the same timeout
    pool_recycle = settings.DB_POOL_RECYCLE  # Keep the same recycle time
    pool_pre_ping = True  # Always enable pre-ping in production
    echo = False  # Disable SQL logging in production
    echo_pool = False  # Disable pool logging in production
elif is_test:
    # Test environment - minimal pool
    pool_size = 2  # Minimal pool size for tests
    max_overflow = 0  # No overflow for tests
    pool_timeout = 5  # Short timeout for tests
    pool_recycle = 300  # Short recycle time for tests
    pool_pre_ping = True  # Enable pre-ping for tests
    echo = False  # Disable SQL logging in tests to improve performance
    echo_pool = False  # Disable pool logging in tests
else:
    # Development environment - use settings as defined
    pool_size = settings.DB_POOL_SIZE
    max_overflow = settings.DB_MAX_OVERFLOW
    pool_timeout = settings.DB_POOL_TIMEOUT
    pool_recycle = settings.DB_POOL_RECYCLE
    pool_pre_ping = True
    echo = settings.DEBUG  # Use debug setting for SQL logging
    echo_pool = False  # Disable pool logging to reduce noise

# Engine performance optimization options
engine_options = {
    # Common options for all environments
    "pool_size": pool_size,
    "max_overflow": max_overflow,
    "pool_timeout": pool_timeout,
    "pool_recycle": pool_recycle,
    "pool_pre_ping": pool_pre_ping,
    "echo": echo,
    "echo_pool": echo_pool,
    # Disable logging name to reduce logging overhead
    "logging_name": None,
    "pool_logging_name": None,
    # Performance optimizations
    "execution_options": {
        "isolation_level": "READ COMMITTED",  # Default isolation level
        "compiled_cache": None  # Use SQLAlchemy's statement cache
    }
}

# Log pool configuration
logger.info(f"Database pool configuration: environment={environment}, "
            f"pool_size={pool_size}, max_overflow={max_overflow}, "
            f"pool_timeout={pool_timeout}, pool_recycle={pool_recycle}")

# Configure async connection pooling with optimized settings
async_engine = create_async_engine(
    str(settings.DATABASE_URL),
    **engine_options
)

# Configure sync engine
sync_engine = create_engine(
    str(settings.sync_database_url),
    poolclass=QueuePool,
    **engine_options
)

# Add query execution timing
@event.listens_for(sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if context:
        context._query_start_time = time.time()

@event.listens_for(sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if context and hasattr(context, "_query_start_time"):
        execution_time = time.time() - context._query_start_time
        # Log slow queries
        if execution_time > DB_SLOW_QUERY_LOG_SECONDS:
            logger.warning(f"Slow query detected: {execution_time:.4f}s\nQuery: {statement}")
            # Record metrics for slow queries
            metrics.record_slow_query()
            metrics.record_query_time(execution_time)
        # Record query execution time for all queries
        metrics.record_query_time(execution_time)

# Configure session factories with transaction management and performance optimizations
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
def set_database_connection_settings(dbapi_connection, connection_record):
    """Set database-specific connection settings."""
    try:
        cursor = dbapi_connection.cursor()
        # Common settings for all databases
        cursor.execute("SET timezone TO 'UTC'")
        
        # Check if this is a PostgreSQL connection
        if 'postgresql' in str(settings.DATABASE_URL).lower():
            # PostgreSQL-specific settings
            cursor.execute("SET search_path TO public")
            cursor.execute(f"SET idle_in_transaction_session_timeout TO '{settings.DB_IDLE_TIMEOUT * 1000}'")  # Convert to milliseconds
            
            # Set statement timeout to prevent long-running queries
            cursor.execute(f"SET statement_timeout = '{DB_STATEMENT_TIMEOUT_SECONDS * 1000}'")  # Convert to milliseconds
            
            # Set additional PostgreSQL-specific parameters for better performance
            if is_production:
                # Production-specific settings
                cursor.execute("SET work_mem = '64MB'")  # Memory for complex sorts
                cursor.execute("SET maintenance_work_mem = '256MB'")  # Memory for maintenance tasks
                cursor.execute("SET synchronous_commit = 'on'")  # Ensure durability
                # Enable auto-explain for slow queries in production
                cursor.execute("LOAD 'auto_explain'")
                cursor.execute("SET auto_explain.log_min_duration = '1000'")  # Log queries longer than 1 second
                cursor.execute("SET auto_explain.log_analyze = 'true'")
            else:
                # Development settings
                cursor.execute("SET work_mem = '16MB'")
                cursor.execute("SET maintenance_work_mem = '64MB'")
                cursor.execute("SET synchronous_commit = 'on'")
            
            # Performance optimizations for all environments
            cursor.execute("SET random_page_cost = 1.1")  # Assume SSD storage
            cursor.execute("SET effective_io_concurrency = 200")  # Higher for SSD storage
            cursor.execute("SET effective_cache_size = '4GB'")  # Assume 4GB of RAM for DB cache
            
        elif 'sqlite' in str(settings.DATABASE_URL).lower():
            # SQLite-specific performance settings
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = -64000")  # Use up to 64MB memory for caching
            cursor.execute("PRAGMA temp_store = MEMORY")
            cursor.execute("PRAGMA mmap_size = 268435456")  # 256MB memory mapping
            cursor.execute("PRAGMA page_size = 4096")
            cursor.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout on busy
            cursor.execute("PRAGMA foreign_keys = ON")
        
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
def set_async_database_connection_settings(dbapi_connection, connection_record):
    """Set database connection settings for the async engine."""
    try:
        cursor = dbapi_connection.cursor()
        
        # Common settings for all databases
        cursor.execute("SET timezone TO 'UTC'")
        
        # Check if PostgreSQL is used
        if 'postgresql' in str(settings.DATABASE_URL).lower():
            # PostgreSQL-specific settings
            cursor.execute("SET search_path TO public")
            cursor.execute(f"SET idle_in_transaction_session_timeout TO '{settings.DB_IDLE_TIMEOUT * 1000}'")  # Convert to milliseconds
            
            # Set statement timeout to prevent long-running queries
            cursor.execute(f"SET statement_timeout = '{DB_STATEMENT_TIMEOUT_SECONDS * 1000}'")  # Convert to milliseconds
            
            # Set additional PostgreSQL-specific parameters for better performance
            if is_production:
                # Production-specific settings
                cursor.execute("SET work_mem = '64MB'")  # Memory for complex sorts
                cursor.execute("SET maintenance_work_mem = '256MB'")  # Memory for maintenance tasks
                cursor.execute("SET synchronous_commit = 'on'")  # Ensure durability
            else:
                # Development settings
                cursor.execute("SET work_mem = '16MB'")
                cursor.execute("SET maintenance_work_mem = '64MB'")
                cursor.execute("SET synchronous_commit = 'off'")
            
            # Performance optimizations for all environments
            cursor.execute("SET random_page_cost = 1.1")  # Assume SSD storage
            
            # Try to set effective_io_concurrency but handle platform differences gracefully
            try:
                cursor.execute("SET effective_io_concurrency = 200")  # Higher for SSD storage
            except Exception as e:
                logger.info(f"Setting effective_io_concurrency not supported on this platform: {str(e)}")
                # Fallback to a safer value
                try:
                    cursor.execute("SET effective_io_concurrency = 0")
                except Exception:
                    pass  # Ignore if it fails entirely
            
            cursor.execute("SET effective_cache_size = '4GB'")  # Assume 4GB of RAM for DB cache
            
        elif 'sqlite' in str(settings.DATABASE_URL).lower():
            # SQLite-specific performance settings
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = -16000")  # Use 16MB cache (-16000 pages)
            cursor.execute("PRAGMA temp_store = MEMORY")
            
    except Exception as e:
        logger.error(f"Failed to set async database connection parameters: {e}")
        # Do not re-raise, to allow application startup even with suboptimal database settings

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
    """Check database connection health efficiently.
    
    This function performs minimal health checks to avoid creating additional load.
    In production, it will check for critical issues but avoid expensive operations.
    
    Returns:
        bool: True if database connection is healthy, False otherwise
    """
    try:
        # Use a shorter timeout for health checks to prevent blocking
        options = {"timeout": 3.0}
        
        # Use a lightweight connection for basic health check
        async with async_engine.connect().execution_options(**options) as conn:
            # Basic connection test - most lightweight operation possible
            await conn.execute(text("SELECT 1"))
            
            # For AWS health checks, just return True after basic connectivity check
            if os.environ.get("AWS_EXECUTION_ENV") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                return True
            
            # Skip detailed health checks in high traffic periods or if in a stressed state
            if metrics.connection_failures_count > 5 or metrics.slow_queries_count > 10:
                logger.info("Skipping detailed health checks due to recent connection issues")
                return True
            
            # Database-specific health checks
            if 'postgresql' in str(settings.DATABASE_URL).lower():
                # Only run these checks in non-production or if explicitly configured
                if not is_production or settings.ENABLE_DETAILED_HEALTH_CHECKS:
                    try:
                        # Check if the database is in recovery mode (standby)
                        result = await conn.execute(text("SELECT pg_is_in_recovery()"))
                        is_in_recovery = await result.scalar()
                        
                        # Only check for long-running transactions on primary instances
                        # and only in production (less frequently)
                        if not is_in_recovery and is_production and time.time() % 60 < 5:  # Run approximately every minute
                            result = await conn.execute(text("""
                                SELECT count(*) FROM pg_stat_activity 
                                WHERE state = 'active' 
                                AND (now() - xact_start) > '5 minutes'::interval
                                LIMIT 1
                            """))
                            long_running_txns = await result.scalar()
                            
                            if long_running_txns > 0:
                                logger.warning(f"Found {long_running_txns} long-running transactions")
                    except Exception as e:
                        logger.error(f"Error during PostgreSQL specific health checks: {str(e)}")
                        # Don't fail the health check for this specific error
            
            elif 'sqlite' in str(settings.DATABASE_URL).lower():
                # Only run these checks in dev/test or if explicitly configured
                if not is_production or settings.ENABLE_DETAILED_HEALTH_CHECKS:
                    try:
                        # Use quick_check instead of integrity_check for better performance
                        result = await conn.execute(text("PRAGMA quick_check(1)"))
                        check_result = await result.scalar()
                        
                        if check_result != 'ok':
                            logger.warning(f"SQLite quick_check returned: {check_result}")
                    except Exception as e:
                        logger.error(f"Error performing SQLite health checks: {str(e)}")
                        # Don't fail the health check for this specific error
            
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {str(e)}")
        metrics.connection_failures.inc()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during database health check: {str(e)}")
        metrics.connection_failures.inc()
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
