#!/usr/bin/env python
"""
Database Initialization Script for Agentic Deals System

This script is called during container startup to:
1. Create database tables (SQLAlchemy models)
2. Create extensions if needed
3. Report success or failure

It's designed to work with environment variables for database connection.
"""

import os
import sys
import logging
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("init-db")

async def init_db():
    """Initialize the database with required tables and extensions."""
    # Get database connection parameters from environment variables
    db_host = os.environ.get('POSTGRES_HOST')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_user = os.environ.get('POSTGRES_USER')
    db_password = os.environ.get('POSTGRES_PASSWORD')
    db_name = os.environ.get('POSTGRES_DB', 'agentic_deals')
    
    logger.info(f"Initializing database {db_name} at {db_host}:{db_port} as {db_user}")
    
    # Build connection string for asyncpg
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Create engine
    try:
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True
        )
        
        # Create a session
        async with AsyncSession(engine) as session:
            # Check connection
            logger.info("Testing database connection...")
            result = await session.execute(text("SELECT 1 AS test"))
            test_value = result.scalar_one()
            if test_value == 1:
                logger.info("Database connection successful")
            else:
                logger.error(f"Unexpected database test result: {test_value}")
                return False
            
            # Create extensions
            logger.info("Creating database extensions...")
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\""))
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS \"hstore\""))
            await session.commit()
            logger.info("Database extensions created successfully")
            
            # Create tables using SQLAlchemy models
            # First, we need to import the models
            try:
                logger.info("Importing database models...")
                from core.models.base import Base
                # Import all models to ensure they are registered with SQLAlchemy
                from core.models import (
                    User, Goal, Deal, Notification, ChatMessage,
                    TokenTransaction, TokenBalanceHistory, TokenWallet,
                    Market, PricePoint, PriceTracker, PricePrediction,
                    MessageRole, MessageStatus, AuthToken
                )
                
                # Set up model relationships
                from core.models.relationships import setup_relationships
                setup_relationships()
                
                logger.info("Creating database tables...")
                async with engine.begin() as conn:
                    # Only create tables that don't exist
                    await conn.run_sync(Base.metadata.create_all)
                
                logger.info("Database tables created successfully")
                return True
                
            except ImportError as e:
                logger.error(f"Failed to import models: {str(e)}")
                return False
            
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error initializing database: {str(e)}")
        return False

async def verify_db():
    """Verify database setup by checking table count."""
    # Get database connection parameters from environment variables
    db_host = os.environ.get('POSTGRES_HOST')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_user = os.environ.get('POSTGRES_USER')
    db_password = os.environ.get('POSTGRES_PASSWORD')
    db_name = os.environ.get('POSTGRES_DB', 'agentic_deals')
    
    # Build connection string for asyncpg
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Create engine
    try:
        engine = create_async_engine(db_url, echo=False)
        
        # Create a session
        async with AsyncSession(engine) as session:
            # Count tables
            result = await session.execute(text("""
                SELECT count(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar_one()
            logger.info(f"Database has {table_count} tables")
            
            # Get table list
            result = await session.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            logger.info(f"Tables: {', '.join(tables)}")
            
            return table_count > 0
    except Exception as e:
        logger.error(f"Error verifying database: {str(e)}")
        return False

async def main():
    """Main function."""
    # Check if database initialization is required or can be skipped
    if os.environ.get('SKIP_DB_INIT', '').lower() == 'true':
        logger.info("Database initialization skipped as requested")
        sys.exit(0)
    
    # Initialize database
    success = await init_db()
    
    if success:
        # Verify database
        verify_success = await verify_db()
        if verify_success:
            logger.info("Database initialization and verification completed successfully")
            sys.exit(0)
        else:
            logger.error("Database verification failed")
            sys.exit(1)
    else:
        logger.error("Database initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 