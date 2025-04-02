#!/usr/bin/env python
"""
AWS Database Creation Script for Agentic Deals System

This script creates the agentic_deals database if it doesn't exist.
It can also reset the database if the RESET_DB environment variable is set to true.
It's designed to be run as part of the container startup process.
"""

import os
import sys
import time
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("aws-db-creation")

def terminate_database_connections(cursor, db_name, max_retries=5, wait_time=2):
    """
    Terminate all connections to the specified database with retry mechanism.
    
    Args:
        cursor: Database cursor
        db_name: Name of the database
        max_retries: Maximum number of retries to terminate connections
        wait_time: Time to wait between retries in seconds
        
    Returns:
        bool: True if all connections were terminated, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # Get current connection count
            cursor.execute(
                sql.SQL("""
                SELECT COUNT(*) 
                FROM pg_stat_activity 
                WHERE pg_stat_activity.datname = %s
                AND pid <> pg_backend_pid()
                """),
                (db_name,)
            )
            connection_count = cursor.fetchone()[0]
            
            if connection_count == 0:
                logger.info(f"No active connections to '{db_name}' found.")
                return True
                
            logger.info(f"Found {connection_count} active connections to '{db_name}'. Terminating...")
            
            # First, revoke connect permission to prevent new connections
            cursor.execute(
                sql.SQL("""
                REVOKE CONNECT ON DATABASE {} FROM PUBLIC;
                """).format(sql.Identifier(db_name))
            )
            
            # Force close all connections
            cursor.execute(
                sql.SQL("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s
                AND pid <> pg_backend_pid()
                """), 
                (db_name,)
            )
            
            # Wait a bit
            time.sleep(wait_time)
            
            # Check if connections are still active
            cursor.execute(
                sql.SQL("""
                SELECT COUNT(*) 
                FROM pg_stat_activity 
                WHERE pg_stat_activity.datname = %s
                AND pid <> pg_backend_pid()
                """),
                (db_name,)
            )
            remaining_connections = cursor.fetchone()[0]
            
            if remaining_connections == 0:
                logger.info(f"Successfully terminated all connections to '{db_name}'.")
                return True
            
            logger.warning(f"Still {remaining_connections} connections active after attempt {attempt+1}. Retrying...")
        
        except Exception as e:
            logger.error(f"Error while terminating connections: {str(e)}")
        
        # If we've reached here, we need to try again
        time.sleep(wait_time)
    
    # If we've exhausted all retries
    logger.error(f"Failed to terminate all connections to '{db_name}' after {max_retries} attempts.")
    return False

def create_or_reset_database():
    """Create the agentic_deals database if it doesn't exist or reset it if RESET_DB is true."""
    db_host = os.environ.get('POSTGRES_HOST')
    db_port = os.environ.get('POSTGRES_PORT', '5432')
    db_user = os.environ.get('POSTGRES_USER')
    db_password = os.environ.get('POSTGRES_PASSWORD')
    db_name = os.environ.get('POSTGRES_DB', 'agentic_deals')
    
    # Check if we should reset the database
    reset_db = os.environ.get('RESET_DB', '').lower() == 'true'
    
    logger.info("=== DATABASE RESET LOG ===")
    logger.info(f"Database management: host={db_host}, port={db_port}, database={db_name}")
    logger.info(f"Database reset flag: RESET_DB={reset_db}")
    
    # First connect to postgres database
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
            if reset_db:
                logger.info(f"DATABASE RESET: Database '{db_name}' exists and will be reset")
                
                # Terminate all connections to the database using the improved function
                logger.info(f"DATABASE RESET: Terminating all connections to '{db_name}'...")
                if not terminate_database_connections(cursor, db_name):
                    logger.error("Failed to terminate all database connections. Aborting reset.")
                    return False
                
                # Drop the database
                logger.info(f"DATABASE RESET: Dropping database '{db_name}'...")
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
                logger.info(f"DATABASE RESET: Database '{db_name}' dropped successfully.")
                
                # Create the database
                logger.info(f"DATABASE RESET: Creating fresh database '{db_name}'...")
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                logger.info(f"DATABASE RESET: Fresh database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists. Reset not requested.")
        else:
            logger.info(f"DATABASE CREATION: Database '{db_name}' does not exist, creating new...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            logger.info(f"DATABASE CREATION: New database '{db_name}' created successfully.")
        
        cursor.close()
        conn.close()
        logger.info("=== DATABASE MANAGEMENT COMPLETED SUCCESSFULLY ===")
        return True
    except Exception as e:
        logger.error(f"DATABASE ERROR: Failed to manage database: {str(e)}")
        return False

def main():
    """Main function to create or reset the database."""
    logger.info("Starting database creation/reset process")
    
    if create_or_reset_database():
        logger.info("Database creation/reset process completed successfully")
        sys.exit(0)
    else:
        logger.error("Database creation/reset failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 