"""Database configuration and session management.

This module provides database connection setup, session management, and connection pooling
for the AI Agentic Deals System. It includes retry logic and monitoring capabilities.
"""

from __future__ import annotations
import inspect
import logging
import os
import time
import traceback
import weakref
import asyncio
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple, Union, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import event, text

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
    # Production pool settings - reduce pool size to prevent connection exhaustion
    pool_size = min(settings.DB_POOL_SIZE, 15)  # Reduced from 25 to prevent connection exhaustion
    max_overflow = min(settings.DB_MAX_OVERFLOW, 10)  # Reduced from 25 to prevent connection exhaustion
    pool_timeout = max(settings.DB_POOL_TIMEOUT, 30)  # Reduced from 60 to fail faster
    pool_recycle = min(settings.DB_POOL_RECYCLE, 300)  # Reduced from 600 to recycle connections more aggressively
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
    # Development environment - optimized to prevent connection exhaustion
    pool_size = 20  # Reduced from 40 to prevent connection exhaustion
    max_overflow = 20  # Reduced from 60 to prevent connection exhaustion
    pool_timeout = 30  # Reduced from 90 to fail faster
    pool_recycle = 180  # Reduced from 240 to recycle connections more aggressively
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
        "compiled_cache": None,  # Use SQLAlchemy's statement cache
        "connect_args": {
            "application_name": "agentic_deals_backend",  # Add application name for better logging
            "options": "-c statement_timeout=10000"  # 10 seconds statement timeout
        }
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
    """Get database session with enhanced connection management.
    
    This dependency provides a database session that ensures connections are 
    properly closed even in failure scenarios to prevent connection leaks.
    """
    session = AsyncSessionLocal()
    try:
        # Start a fresh session with each request
        yield session
        
        # Explicitly commit changes if no exception occurred
        try:
            await session.commit()
        except Exception as commit_error:
            logger.error(f"Error committing session: {str(commit_error)}")
            await session.rollback()
            raise
    except SQLAlchemyError as db_error:
        # Catch database-specific errors
        logger.error(f"Database error in session: {str(db_error)}")
        await session.rollback()
        metrics.connection_failures.inc()
        raise
    except Exception as e:
        # Catch all other errors
        logger.error(f"Unexpected error in database session: {str(e)}")
        await session.rollback()
        raise
    finally:
        # Always make sure the session is closed
        try:
            await session.close()
            logger.debug("Database session closed successfully")
        except Exception as close_error:
            logger.error(f"Error closing database session: {str(close_error)}")
            # Even in case of error while closing, consider the session disposed
            # to prevent connection leaks

async def get_async_db_session() -> AsyncSession:
    """Get async database session.
    
    WARNING: This function is maintained for backward compatibility.
    New code should use get_async_db_context() instead for proper session management.
    
    This version wraps the context manager to ensure sessions are properly tracked and closed.
    
    Returns:
        AsyncSession: Database session with enhanced tracking and cleanup
    """
    # Log a warning about using the deprecated function
    current_frame = inspect.currentframe()
    caller_frame = inspect.getouterframes(current_frame, 2)
    caller_info = f"{caller_frame[1][1]}:{caller_frame[1][2]} in {caller_frame[1][3]}"
    logger.warning(f"Deprecated get_async_db_session() called from {caller_info}. Use get_async_db_context() instead.")
    
    # Create a session with enhanced tracking
    session = AsyncSessionLocal()
    
    # Register a cleanup function to be called when the session is garbage collected
    # This provides a safety net for sessions that aren't properly closed
    async def cleanup_session(session_ref):
        session = session_ref()
        if session:
            try:
                logger.warning(f"Cleaning up unclosed session from {caller_info} during garbage collection")
                if not session.is_active:
                    await session.close()
            except Exception as e:
                logger.error(f"Error during session cleanup: {str(e)}")
    
    # Use weakref to avoid circular references
    session_ref = weakref.ref(session)
    asyncio.create_task(cleanup_session(session_ref))
    
    return session

# Create the improved version as a context manager to ensure proper cleanup
@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session as a context manager.
    
    This function provides a context manager for database sessions, ensuring proper cleanup.
    It should be used with async with:
    
    async with get_async_db_context() as session:
        # Use session here
    
    Yields:
        AsyncSession: Database session that will be automatically closed
    """
    session = None
    try:
        # Get the current stack frame for better debugging of connection leaks
        current_frame = inspect.currentframe()
        caller_frame = inspect.getouterframes(current_frame, 2)
        caller_info = f"{caller_frame[1][1]}:{caller_frame[1][2]} in {caller_frame[1][3]}"
        
        # Create a new session
        session = AsyncSessionLocal()
        logger.debug(f"Database session created by {caller_info}")
        
        # Track metrics
        metrics.connection_checkouts.inc()
        
        yield session
        
        # Commit changes if no exception occurred
        await session.commit()
        logger.debug(f"Database session committed by {caller_info}")
        
    except SQLAlchemyError as db_error:
        # Catch database-specific errors
        if session:
            await session.rollback()
        logger.error(f"Database error in session from {caller_info}: {str(db_error)}")
        metrics.connection_failures.inc()
        raise
    except Exception as e:
        # Catch all other errors
        if session:
            await session.rollback()
        logger.error(f"Unexpected error in database session from {caller_info}: {str(e)}")
        raise
    finally:
        # Always make sure the session is closed
        if session:
            try:
                await session.close()
                logger.debug(f"Database session closed successfully from {caller_info}")
                metrics.connection_checkins.inc()
            except Exception as close_error:
                logger.error(f"Error closing database session from {caller_info}: {str(close_error)}")

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
    It focuses on basic connectivity to ensure the database is reachable.
    
    Returns:
        bool: True if database connection is healthy, False otherwise
    """
    try:
        # Use a shorter timeout for health checks to prevent blocking
        options = {"timeout": 3.0}
        
        # Use a lightweight connection for basic health check
        # Properly await the connect method and execution_options
        conn = await async_engine.connect()
        conn = await conn.execution_options(**options)
        
        try:
            # Basic connection test - most lightweight operation possible
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            
            # Verify we got the expected result
            if value != 1:
                logger.warning(f"Database health check returned unexpected value: {value}")
                await conn.close()
                return False
                
            logger.debug("Database health check passed")
            await conn.close()
            return True
            
        except Exception as e:
            # Make sure to close the connection even if there's an error
            await conn.close()
            raise e
            
    except Exception as e:
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

async def cleanup_idle_connections() -> int:
    """
    Identify and clean up idle database connections.
    
    This function is designed to be called periodically to prevent connection pool exhaustion.
    It identifies connections that have been idle for too long and closes them.
    
    Returns:
        int: Number of connections cleaned up
    """
    session = None
    try:
        # For PostgreSQL, we can use pg_stat_activity to find idle connections
        if 'postgresql' in str(settings.DATABASE_URL).lower():
            session = AsyncSessionLocal()
            # Query to find idle connections for our application
            # This looks for connections that have been idle for more than 5 minutes (300 seconds)
            # Reduced from 600 seconds to be more aggressive
            query = text("""
                SELECT pid, application_name, state, usename, 
                       client_addr, backend_start, xact_start, state_change,
                       EXTRACT(EPOCH FROM (now() - state_change)) as idle_seconds
                FROM pg_stat_activity 
                WHERE (application_name LIKE 'agentic_deals%' OR application_name = 'psql')
                  AND state IN ('idle', 'idle in transaction')
                  AND EXTRACT(EPOCH FROM (now() - state_change)) > 300
                ORDER BY idle_seconds DESC
            """)
            
            result = await session.execute(query)
            idle_connections = result.all()
            
            # Log which connections will be terminated
            logger.info(f"Found {len(idle_connections)} idle connections to clean up")
            
            count = 0
            # Terminate each idle connection
            for conn in idle_connections:
                try:
                    # Use pg_terminate_backend to safely terminate the connection
                    # Log detailed information about the connection being terminated
                    logger.info(f"Terminating idle connection: pid={conn.pid}, user={conn.usename}, " 
                                f"addr={conn.client_addr}, state={conn.state}, "
                                f"idle_time={conn.idle_seconds:.1f}s, "
                                f"backend_start={conn.backend_start}, state_change={conn.state_change}")
                    
                    terminate_query = text(f"SELECT pg_terminate_backend({conn.pid})")
                    await session.execute(terminate_query)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to terminate connection {conn.pid}: {str(e)}")
            
            # Find long-running transactions that might be blocking other operations
            long_tx_query = text("""
                SELECT pid, application_name, query, state, usename, 
                       EXTRACT(EPOCH FROM (now() - xact_start)) as tx_seconds
                FROM pg_stat_activity 
                WHERE xact_start IS NOT NULL
                  AND EXTRACT(EPOCH FROM (now() - xact_start)) > 300
                ORDER BY tx_seconds DESC
            """)
            
            tx_result = await session.execute(long_tx_query)
            long_txs = tx_result.all()
            
            if long_txs:
                logger.warning(f"Found {len(long_txs)} long-running transactions (>5 min)")
                for tx in long_txs:
                    logger.warning(f"Long TX: pid={tx.pid}, user={tx.usename}, time={tx.tx_seconds:.1f}s, query={tx.query[:100]}...")
            
            # Commit the changes
            await session.commit()
            
            # Record metrics
            metrics.idle_connections_cleaned.inc(count)
            return count
        else:
            # For other database types, we currently don't have a specific cleanup mechanism
            logger.debug("Connection cleanup is only supported for PostgreSQL databases")
            return 0
    
    except Exception as e:
        logger.error(f"Failed to clean up idle connections: {str(e)}")
        if session:
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error rolling back session in cleanup_idle_connections: {str(rollback_error)}")
        return 0
    finally:
        # Always close the session
        if session:
            try:
                await session.close()
                logger.debug("Database session closed successfully in cleanup_idle_connections")
            except Exception as close_error:
                logger.error(f"Error closing session in cleanup_idle_connections: {str(close_error)}")

async def cleanup_all_connections() -> None:
    """
    Aggressively clean up all database connections.
    
    This function is designed to be called during application shutdown to ensure
    all database connections are properly closed. It combines various cleanup
    approaches to maximize the chance of successful cleanup.
    
    Returns:
        None
    """
    try:
        logger.info("Starting aggressive cleanup of all database connections")
        
        # First try to use pg_terminate_backend to close idle connections
        idle_connections_closed = await cleanup_idle_connections()
        logger.info(f"Cleaned up {idle_connections_closed} idle connections via pg_terminate_backend")
        
        # Next, try to dispose the engine pools
        try:
            logger.info("Disposing async engine pool")
            await async_engine.dispose()
            logger.info("Async engine pool disposed successfully")
        except Exception as async_error:
            logger.error(f"Error disposing async engine pool: {str(async_error)}")
            
        try:
            logger.info("Disposing sync engine pool")
            sync_engine.dispose()
            logger.info("Sync engine pool disposed successfully")
        except Exception as sync_error:
            logger.error(f"Error disposing sync engine pool: {str(sync_error)}")
            
        # Direct PostgreSQL cleanup as a last resort
        if 'postgresql' in str(settings.DATABASE_URL).lower():
            try:
                logger.info("Performing direct PostgreSQL connection cleanup")
                # Create a new session for this cleanup operation
                session = AsyncSessionLocal()
                
                # Get our application's connection count
                query = text("""
                    SELECT COUNT(*) as conn_count
                    FROM pg_stat_activity 
                    WHERE application_name LIKE '%agentic_deals%'
                """)
                
                result = await session.execute(query)
                conn_count = result.scalar() or 0
                
                logger.info(f"Found {conn_count} connections for this application")
                
                # If we still have connections, try to terminate all of them
                if conn_count > 0:
                    logger.warning(f"Terminating all {conn_count} remaining connections")
                    terminate_query = text("""
                        SELECT pg_terminate_backend(pid) 
                        FROM pg_stat_activity 
                        WHERE application_name LIKE '%agentic_deals%'
                    """)
                    
                    await session.execute(terminate_query)
                    await session.commit()
                    logger.info("Terminated all application connections")
                
                # Close this cleanup session
                await session.close()
                
            except Exception as pg_error:
                logger.error(f"Error in direct PostgreSQL cleanup: {str(pg_error)}")
        
        logger.info("Aggressive database connection cleanup completed")
        
    except Exception as e:
        logger.error(f"Failed during aggressive connection cleanup: {str(e)}")
        
__all__ = ['Base', 'async_engine', 'get_session', 'cleanup_idle_connections', 'cleanup_all_connections']
