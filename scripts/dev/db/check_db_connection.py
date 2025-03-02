"""Script to check database connections.

This script checks database connections for both Docker and localhost configurations.
"""

import sys
import logging
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_docker_connection():
    """Check connection to the database in Docker."""
    logger.info("Checking connection to database in Docker...")
    
    try:
        # Use docker exec to run a query in the postgres container
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'deals', '-c', 'SELECT 1 as test'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "1 row" in result.stdout:
            logger.info("✅ Successfully connected to database in Docker!")
            
            # Check for tables
            result = subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'deals', '-c', 
                 "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse the output to get table names
            lines = result.stdout.strip().split('\n')
            if len(lines) > 2:  # Header + separator + at least one table
                # Skip header and separator lines
                table_lines = lines[2:-1]  # Skip the last line which is the row count
                tables = [line.strip() for line in table_lines]
                
                if tables:
                    logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
                else:
                    logger.warning("No tables found in the database. Migrations may not have been applied.")
            else:
                logger.warning("No tables found in the database. Migrations may not have been applied.")
                
            return True
        else:
            logger.error("Connection test failed")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to connect to database in Docker: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error checking Docker connection: {str(e)}")
        return False

def check_localhost_connection():
    """Check connection to the database on localhost."""
    logger.info("Checking connection to database on localhost...")
    
    try:
        # Try to connect to the database on localhost
        engine = create_engine('postgresql://postgres:12345678@localhost:5432/deals')
        conn = engine.connect()
        
        # Execute a simple query
        result = conn.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        
        if row and row[0] == 1:
            logger.info("✅ Successfully connected to database on localhost!")
            
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
        logger.error(f"Failed to connect to database on localhost: {str(e)}")
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
        localhost_success = check_localhost_connection()
        success = success and localhost_success
        
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