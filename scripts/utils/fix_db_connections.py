#!/usr/bin/env python
"""
Database Connection Utility Script

This script helps diagnose and resolve database connection issues,
particularly the "too many clients" error in PostgreSQL.
It identifies idle connections and provides options to close them.

Usage:
    python fix_db_connections.py [--force-close] [--all] [--min-idle-seconds=600]

Options:
    --force-close     Automatically close idle connections
    --all             Consider all connections, not just those from this application
    --min-idle-seconds=600    Minimum idle time in seconds (default: 600, 10 minutes)
"""

import os
import sys
import argparse
import asyncio
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import from core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import settings
try:
    from core.config import settings
    from core.database import cleanup_idle_connections
except ImportError:
    logger.error("Could not import required modules. Make sure you're running from the project root.")
    sys.exit(1)

def get_db_connection_info():
    """Extract database connection information from settings."""
    db_url = str(settings.DATABASE_URL)
    
    # For PostgreSQL URLs
    if 'postgresql' in db_url.lower():
        # Parse connection info
        try:
            # Handle different URL formats
            if '@' in db_url:
                # Extract host and port
                host_part = db_url.split('@')[1].split('/')[0]
                if ':' in host_part:
                    host, port = host_part.split(':')
                else:
                    host = host_part
                    port = '5432'  # Default PostgreSQL port
                
                # Extract database name
                db_name = db_url.split('/')[-1].split('?')[0]
                
                return {
                    'type': 'postgresql',
                    'host': host,
                    'port': port,
                    'dbname': db_name
                }
        except Exception as e:
            logger.error(f"Failed to parse database URL: {str(e)}")
    
    # For SQLite URLs
    elif 'sqlite' in db_url.lower():
        return {
            'type': 'sqlite',
            'path': db_url.replace('sqlite:///', '')
        }
    
    # Default or unsupported
    return {
        'type': 'unknown',
        'url': db_url
    }

async def diagnose_connections(force_close=False, all_connections=False, min_idle_seconds=600):
    """
    Diagnose database connection issues and optionally close idle connections.
    
    Args:
        force_close (bool): Whether to automatically close idle connections
        all_connections (bool): Whether to consider all connections, not just from this app
        min_idle_seconds (int): Minimum idle time in seconds to consider closing
    """
    db_info = get_db_connection_info()
    
    if db_info['type'] != 'postgresql':
        logger.error("This script only supports PostgreSQL databases")
        sys.exit(1)
    
    # Create a direct connection to the database
    engine = create_engine(str(settings.sync_database_url))
    Session = sessionmaker(engine)
    
    with Session() as session:
        try:
            # Get total connection limit
            max_connections_result = session.execute(text("SHOW max_connections")).scalar()
            logger.info(f"Database max connections: {max_connections_result}")
            
            # Get current connection count
            current_count_result = session.execute(
                text("SELECT count(*) FROM pg_stat_activity")
            ).scalar()
            logger.info(f"Current connection count: {current_count_result}")
            
            # Get connection usage percentage
            usage_pct = (int(current_count_result) / int(max_connections_result)) * 100
            logger.info(f"Connection usage: {usage_pct:.1f}%")
            
            # Warning level
            if usage_pct > 80:
                logger.warning("⚠️ HIGH CONNECTION USAGE: Database is approaching connection limit")
            
            # Get idle connections
            if all_connections:
                # All idle connections
                query = text(f"""
                    SELECT pid, application_name, usename, client_addr, 
                        state, query, backend_start,
                        EXTRACT(EPOCH FROM (now() - state_change)) as idle_seconds,
                        EXTRACT(EPOCH FROM (now() - backend_start)) as conn_seconds
                    FROM pg_stat_activity 
                    WHERE state = 'idle'
                    AND EXTRACT(EPOCH FROM (now() - state_change)) > {min_idle_seconds}
                    ORDER BY idle_seconds DESC
                """)
            else:
                # Only our application's connections
                query = text(f"""
                    SELECT pid, application_name, usename, client_addr, 
                        state, query, backend_start,
                        EXTRACT(EPOCH FROM (now() - state_change)) as idle_seconds,
                        EXTRACT(EPOCH FROM (now() - backend_start)) as conn_seconds
                    FROM pg_stat_activity 
                    WHERE application_name LIKE 'ai-agentic-deals%'
                    AND state = 'idle'
                    AND EXTRACT(EPOCH FROM (now() - state_change)) > {min_idle_seconds}
                    ORDER BY idle_seconds DESC
                """)
            
            idle_connections = session.execute(query).fetchall()
            
            if not idle_connections:
                logger.info("No idle connections found matching criteria")
                return
            
            logger.info(f"Found {len(idle_connections)} idle connections:")
            for i, conn in enumerate(idle_connections, 1):
                logger.info(
                    f"{i}. PID: {conn.pid}, App: {conn.application_name}, "
                    f"User: {conn.usename}, Idle: {timedelta(seconds=int(conn.idle_seconds))}, "
                    f"Connected: {timedelta(seconds=int(conn.conn_seconds))}"
                )
            
            # Close connections if requested
            if force_close and idle_connections:
                logger.info(f"Closing {len(idle_connections)} idle connections...")
                closed_count = 0
                
                for conn in idle_connections:
                    try:
                        session.execute(text(f"SELECT pg_terminate_backend({conn.pid})"))
                        logger.info(f"✓ Closed connection: PID {conn.pid}")
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to close connection {conn.pid}: {str(e)}")
                
                logger.info(f"Successfully closed {closed_count} connections")
                
            elif idle_connections and not force_close:
                logger.info("To close these connections, run with --force-close")
        
        except Exception as e:
            logger.error(f"Error diagnosing connections: {str(e)}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Database connection diagnostic tool")
    parser.add_argument("--force-close", action="store_true", help="Automatically close idle connections")
    parser.add_argument("--all", action="store_true", help="Consider all connections, not just from this app")
    parser.add_argument("--min-idle-seconds", type=int, default=600, help="Minimum idle time in seconds")
    
    args = parser.parse_args()
    
    # Run the async function
    asyncio.run(diagnose_connections(
        force_close=args.force_close,
        all_connections=args.all,
        min_idle_seconds=args.min_idle_seconds
    ))

if __name__ == "__main__":
    main() 