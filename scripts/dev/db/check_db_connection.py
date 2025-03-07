"""Script to check database connections.

This script checks database connections for both Docker and localhost configurations.
"""

import sys
import logging
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import subprocess
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_docker_connection():
    """Check database connection using Docker."""
    try:
        # Check if Docker is running
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print("Docker is not running or not accessible")
            return False
        
        # Check if postgres container is running
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=deals_postgres', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if 'deals_postgres' not in result.stdout:
            print("PostgreSQL container 'deals_postgres' is not running")
            return False
        
        # Try to connect to the database
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 'SELECT 1 as test'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Failed to connect to database: {result.stderr}")
            
            # Try to check if database exists
            result = subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c',
                 "SELECT datname FROM pg_database WHERE datname = 'agentic_deals'"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if 'agentic_deals' not in result.stdout:
                print("Database 'agentic_deals' does not exist")
            
            return False
        
        print("Successfully connected to database via Docker")
        return True
        
    except Exception as e:
        print(f"Error checking Docker connection: {str(e)}")
        return False

def check_local_connection():
    """Check database connection using local connection."""
    try:
        # Get database connection parameters from environment variables
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_name = os.environ.get('DB_NAME', 'agentic_deals')
        
        # Try to connect using psql
        result = subprocess.run(
            ['psql', f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}', '-c', 'SELECT 1 as test'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Failed to connect to database: {result.stderr}")
            return False
        
        print(f"Successfully connected to database at {db_host}:{db_port}")
        return True
        
    except Exception as e:
        print(f"Error checking local connection: {str(e)}")
        return False

def check_custom_connection(host, port, user, password, dbname):
    """Check connection to a custom database configuration."""
    logger.info(f"Checking connection to database at {host}:{port}...")
    
    try:
        # Try to connect to the database with custom parameters
        engine = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{dbname}')
        conn = engine.connect()
        
        # Execute a simple query
        result = conn.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        
        if row and row[0] == 1:
            logger.info(f"✅ Successfully connected to database at {host}:{port}!")
            
            # Check for tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            
            if tables:
                logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
            else:
                logger.warning("No tables found in the database. Migrations may not have been applied.")
                
            conn.close()
            engine.dispose()
            return True
        else:
            logger.error("Connection test failed")
            return False
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to connect to database at {host}:{port}: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check database connections')
    parser.add_argument('--mode', choices=['docker', 'localhost', 'custom', 'all'], default='all',
                        help='Connection mode to check (default: all)')
    parser.add_argument('--host', default='localhost', help='Database host (for custom mode)')
    parser.add_argument('--port', default='5432', help='Database port (for custom mode)')
    parser.add_argument('--user', default='postgres', help='Database user (for custom mode)')
    parser.add_argument('--password', default='12345678', help='Database password (for custom mode)')
    parser.add_argument('--dbname', default='deals', help='Database name (for custom mode)')
    
    args = parser.parse_args()
    
    success = True
    
    if args.mode in ['docker', 'all']:
        docker_success = check_docker_connection()
        success = success and docker_success
        
    if args.mode in ['localhost', 'all']:
        local_success = check_local_connection()
        success = success and local_success
        
    if args.mode == 'custom':
        custom_success = check_custom_connection(
            args.host, args.port, args.user, args.password, args.dbname
        )
        success = success and custom_success
    
    if success:
        logger.info("All connection checks passed!")
        sys.exit(0)
    else:
        logger.error("One or more connection checks failed.")
        sys.exit(1) 