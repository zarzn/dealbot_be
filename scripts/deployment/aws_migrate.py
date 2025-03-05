#!/usr/bin/env python
"""
AWS Database Migration Script for Agentic Deals System

This script runs database migrations in AWS environment.
It's designed to be run as a one-time task in ECS.
"""

import os
import sys
import logging
import time
import subprocess
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("aws-migration")

def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    db_host = os.environ.get('POSTGRES_HOST')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_user = os.environ.get('POSTGRES_USER')
    db_password = os.environ.get('POSTGRES_PASSWORD')
    db_name = os.environ.get('POSTGRES_DB', 'agentic_deals')
    
    logger.info(f"Checking if database '{db_name}' exists...")
    
    # First connect to postgres database to check if agentic_deals exists
    try:
        # Connect to postgres database
        logger.debug(f"Connecting to postgres database at {db_host}:{db_port} as {db_user}")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if the database exists
        cursor.execute(sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), (db_name,))
        exists = cursor.fetchone()
        
        if exists:
            logger.info(f"Database '{db_name}' already exists.")
        else:
            logger.info(f"Creating database '{db_name}'...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            logger.info(f"Database '{db_name}' created successfully.")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to create database: {str(e)}")
        return False

def wait_for_database(max_retries=30, retry_interval=2):
    """Wait for the database to be available."""
    db_host = os.environ.get('POSTGRES_HOST')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_user = os.environ.get('POSTGRES_USER')
    db_password = os.environ.get('POSTGRES_PASSWORD')
    db_name = os.environ.get('POSTGRES_DB')
    
    connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    logger.info(f"Waiting for database at {db_host}:{db_port}...")
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection successful!")
                return True
        except OperationalError as e:
            logger.warning(f"Database not available yet (attempt {attempt+1}/{max_retries}): {str(e)}")
            time.sleep(retry_interval)
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {str(e)}")
            time.sleep(retry_interval)
    
    logger.error(f"Failed to connect to database after {max_retries} attempts")
    return False

def run_migrations():
    """Run Alembic migrations."""
    try:
        logger.info("Running database migrations...")
        # Try to install psycopg2-binary if it's not already installed
        try:
            import psycopg2
        except ImportError:
            logger.info("Installing psycopg2-binary...")
            subprocess.run(['pip', 'install', 'psycopg2-binary'], check=True)
            
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Migration output:\n{result.stdout}")
        logger.info("Database migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {str(e)}")
        return False

def create_initial_data():
    """Create initial data if needed."""
    try:
        logger.info("Creating initial data...")
        # Check if initial data script exists
        if os.path.exists("scripts/create_initial_data.py"):
            result = subprocess.run(
                ['python', '-m', 'scripts.create_initial_data'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Initial data creation output:\n{result.stdout}")
            logger.info("Initial data created successfully")
        else:
            logger.info("No initial data script found, skipping")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Initial data creation failed: {e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during initial data creation: {str(e)}")
        return False

def main():
    """Main function to run migrations in AWS."""
    logger.info("Starting AWS database migration process")
    
    # Create database if it doesn't exist
    if not create_database_if_not_exists():
        logger.error("Failed to create database, aborting migration")
        sys.exit(1)
    
    # Wait for database
    if not wait_for_database():
        logger.error("Database not available, aborting migration")
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        logger.error("Migration failed, aborting")
        sys.exit(1)
    
    # Create initial data
    if not create_initial_data():
        logger.warning("Initial data creation failed, but continuing")
    
    logger.info("AWS database migration process completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main() 