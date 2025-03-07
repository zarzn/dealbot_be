#!/usr/bin/env python
"""Script to initialize the database tables."""

import asyncio
import asyncpg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    """Initialize the database."""
    try:
        # First connect to default postgres database to handle database creation
        sys_conn = await asyncpg.connect(
            user='postgres',
            password='12345678',
            database='postgres',
            host='localhost'
        )
        
        # Check if agentic_deals database exists
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'agentic_deals'"
        )
        
        if exists:
            logger.info("Dropping existing agentic_deals database...")
            # Terminate all connections to the agentic_deals database
            await sys_conn.execute("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = 'agentic_deals'
                AND pid <> pg_backend_pid();
            """)
            # Drop the database
            await sys_conn.execute("DROP DATABASE agentic_deals")
            logger.info("Existing agentic_deals database dropped")
        
        logger.info("Creating agentic_deals database...")
        await sys_conn.execute("CREATE DATABASE agentic_deals")
        await sys_conn.close()
        
        # Now connect to agentic_deals database to initialize extensions and schemas
        conn = await asyncpg.connect(
            user='postgres',
            password='12345678',
            database='agentic_deals',
            host='localhost'
        )
        
        logger.info("Creating required extensions...")
        # Create required PostgreSQL extensions
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
            CREATE EXTENSION IF NOT EXISTS "pgcrypto";
            CREATE EXTENSION IF NOT EXISTS "hstore";
        """)
        
        # Create a test table to verify database access
        logger.info("Creating test table...")
        await conn.execute("""
            CREATE TABLE test_table (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Insert a test row
            INSERT INTO test_table (name) VALUES ('test_entry');
        """)
        
        # Verify the test table
        result = await conn.fetchval("SELECT COUNT(*) FROM test_table")
        logger.info(f"Test table created with {result} row(s)")
        
        # List all tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        logger.info("Current tables in database:")
        for table in tables:
            logger.info(f"- {table['table_name']}")
        
        logger.info("Database initialization completed successfully!")
        await conn.close()
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(init_db()) 