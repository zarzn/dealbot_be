"""Script to setup database with reset, init and migrations.

This script combines the functionality of check_db.py reset, init_db.py, and alembic upgrade
into a single command for easier database setup.
"""

import subprocess
import sys
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by dropping and recreating it."""
    try:
        # Connect to postgres database to drop/create deals database
        engine = create_engine('postgresql://postgres:12345678@localhost:5432/postgres')
        conn = engine.connect()
        conn.execute(text("COMMIT"))  # Close any open transactions
        
        # Drop connections to deals database
        conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname IN ('deals', 'deals_test')
            AND pid <> pg_backend_pid()
        """))
        
        # Drop and recreate databases
        conn.execute(text("DROP DATABASE IF EXISTS deals"))
        conn.execute(text("DROP DATABASE IF EXISTS deals_test"))
        conn.execute(text("CREATE DATABASE deals"))
        conn.execute(text("CREATE DATABASE deals_test"))
        conn.close()
        engine.dispose()
        
        logger.info("Database reset completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset database: {str(e)}")
        return False

def init_database():
    """Initialize database with required extensions and test table."""
    try:
        # Initialize both main and test databases
        for db_name in ['deals', 'deals_test']:
            # Connect to database
            engine = create_engine(f'postgresql://postgres:12345678@localhost:5432/{db_name}')
            conn = engine.connect()
            
            # Set timezone to UTC
            conn.execute(text(f"SET timezone TO 'UTC'"))
            conn.execute(text(f"ALTER DATABASE {db_name} SET timezone TO 'UTC'"))
            
            # Create required extensions
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            
            # Create test table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """))
            
            # Insert test data
            conn.execute(text("INSERT INTO test_table (name) VALUES ('test') ON CONFLICT DO NOTHING"))
            conn.execute(text("COMMIT"))
            
            # List current tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            
            logger.info(f"Current tables in {db_name} database: %s", ", ".join(tables))
            conn.close()
            engine.dispose()
        
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        return False

def run_migrations():
    """Run alembic migrations."""
    try:
        # Get the current working directory
        current_dir = os.getcwd()
        
        # Run migrations for both main and test databases
        for db_name in ['deals', 'deals_test']:
            # Set the database URL in environment
            os.environ['DATABASE_URL'] = f'postgresql://postgres:12345678@localhost:5432/{db_name}'
            
            # Run alembic from the backend directory
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                capture_output=True,
                text=True,
                check=True,
                cwd=current_dir  # Use current directory instead of backend_dir
            )
            logger.info(f"Migrations for {db_name}:\n{result.stdout}")
            
        logger.info("Database migrations completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run migrations: {e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Failed to run migrations: {str(e)}")
        return False

def setup_database():
    """Run complete database setup process."""
    logger.info("Starting database setup process...")
    
    # Step 1: Reset database
    logger.info("Step 1: Resetting database...")
    if not reset_database():
        logger.error("Database reset failed")
        return False
        
    # Step 2: Initialize database
    logger.info("Step 2: Initializing database...")
    if not init_database():
        logger.error("Database initialization failed")
        return False
        
    # Step 3: Run migrations
    logger.info("Step 3: Running migrations...")
    if not run_migrations():
        logger.error("Database migrations failed")
        return False
    
    logger.info("Database setup completed successfully!")
    return True

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1) 