#!/usr/bin/env python
"""
AWS Database Creation Script for Agentic Deals System

This script creates the agentic_deals database if it doesn't exist.
It's designed to be run as a one-time task in ECS before migrations.
"""

import os
import sys
import logging
import time
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

def create_database():
    """Create the agentic_deals database if it doesn't exist."""
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

def main():
    """Main function to create the database in AWS."""
    logger.info("Starting AWS database creation process")
    
    if create_database():
        logger.info("Database creation process completed successfully")
        sys.exit(0)
    else:
        logger.error("Database creation failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 