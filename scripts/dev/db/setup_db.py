"""Script to setup database with reset, init and migrations.

This script combines the functionality of check_db.py reset, init_db.py, and alembic upgrade
into a single command for easier database setup. It supports both Docker and local environments.
"""

import subprocess
import sys
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from passlib.context import CryptContext
from uuid import uuid4
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

def reset_database_docker():
    """Reset the database by dropping and recreating it using Docker."""
    try:
        # Use docker exec to run commands in the postgres container
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname IN ('deals', 'deals_test') AND pid <> pg_backend_pid()"],
            check=True
        )
        
        # Drop and recreate databases
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "DROP DATABASE IF EXISTS deals"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "DROP DATABASE IF EXISTS deals_test"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "CREATE DATABASE deals"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "CREATE DATABASE deals_test"],
            check=True
        )
        
        logger.info("Database reset completed successfully (Docker)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset database (Docker): {str(e)}")
        return False

def reset_database_local():
    """Reset the database by dropping and recreating it using local connection."""
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
        
        logger.info("Database reset completed successfully (Local)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset database (Local): {str(e)}")
        return False

def init_database_docker():
    """Initialize database with required extensions and test table using Docker."""
    try:
        # Initialize both main and test databases
        for db_name in ['deals', 'deals_test']:
            # Set timezone to UTC
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 f"SET timezone TO 'UTC'"],
                check=True
            )
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 f"ALTER DATABASE {db_name} SET timezone TO 'UTC'"],
                check=True
            )
            
            # Create required extensions
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""],
                check=True
            )
            
            # Create test table
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 "CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name TEXT NOT NULL)"],
                check=True
            )
            
            # Insert test data
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 "INSERT INTO test_table (name) VALUES ('test') ON CONFLICT DO NOTHING"],
                check=True
            )
            
            # List current tables
            result = subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', db_name, '-c', 
                 "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Current tables in {db_name} database (Docker): {result.stdout}")
        
        logger.info("Database initialization completed successfully (Docker)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database (Docker): {str(e)}")
        return False

def init_database_local():
    """Initialize database with required extensions and test table using local connection."""
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
            
            logger.info(f"Current tables in {db_name} database (Local): %s", ", ".join(tables))
            conn.close()
            engine.dispose()
        
        logger.info("Database initialization completed successfully (Local)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database (Local): {str(e)}")
        return False

def run_migrations_docker():
    """Run alembic migrations using Docker."""
    try:
        # Run migrations for both main and test databases
        for db_name in ['deals', 'deals_test']:
            # Run alembic inside the Docker container
            result = subprocess.run(
                ['docker', 'exec', 'deals_backend', 'bash', '-c', 
                 f'cd /app && DATABASE_URL=postgresql://postgres:12345678@deals_postgres:5432/{db_name} alembic upgrade head'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Migrations for {db_name} (Docker):\n{result.stdout}")
            
        logger.info("Database migrations completed successfully (Docker)")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run migrations (Docker): {e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Failed to run migrations (Docker): {str(e)}")
        return False

def run_migrations_local():
    """Run alembic migrations using local connection."""
    try:
        # Get the current working directory
        current_dir = os.getcwd()
        
        # Get the parent directory (backend) where alembic.ini is located
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        
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
                cwd=backend_dir  # Use backend directory where alembic.ini is located
            )
            logger.info(f"Migrations for {db_name} (Local):\n{result.stdout}")
            
        logger.info("Database migrations completed successfully (Local)")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run migrations (Local): {e.stdout}\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Failed to run migrations (Local): {str(e)}")
        return False

def create_default_user_docker():
    """Create a default user in the database using Docker."""
    try:
        # Use docker exec to run SQL commands in the postgres container
        # First check if user already exists
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'deals', '-c', 
             "SELECT id FROM users WHERE email = 'gluked@gmail.com'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If user exists, skip creation
        if "0 rows" not in result.stdout:
            logger.info("Default user already exists, skipping creation (Docker)")
            return True
        
        # Create default user
        hashed_password = get_password_hash("Qwerty123!")
        user_id = str(uuid4())
        
        # Insert user into database
        insert_query = f"""
        INSERT INTO users (
            id, email, name, password, status, preferences, notification_channels,
            email_verified, created_at, updated_at
        ) VALUES (
            '{user_id}', 'gluked@gmail.com', 'Anton M', '{hashed_password}', 'active', '{{}}', '[]',
            TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'deals', '-c', insert_query],
            check=True
        )
        
        logger.info("Default user created successfully (Docker)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create default user (Docker): {str(e)}")
        return False

def create_default_user_local():
    """Create a default user in the database using local connection."""
    try:
        # Connect to the database
        engine = create_engine('postgresql://postgres:12345678@localhost:5432/deals')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if user already exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'gluked@gmail.com'"))
        user = result.fetchone()
        
        if user:
            logger.info("Default user already exists, skipping creation (Local)")
            session.close()
            engine.dispose()
            return True
        
        # Create default user
        hashed_password = get_password_hash("Qwerty123!")
        user_id = str(uuid4())
        
        # Insert user into database
        session.execute(
            text("""
            INSERT INTO users (
                id, email, name, password, status, preferences, notification_channels,
                email_verified, created_at, updated_at
            ) VALUES (
                :id, :email, :name, :password, :status, :preferences, :notification_channels,
                :email_verified, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """),
            {
                "id": user_id,
                "email": "gluked@gmail.com",
                "name": "Anton M",
                "password": hashed_password,
                "status": "active",
                "preferences": "{}",
                "notification_channels": "[]",
                "email_verified": True
            }
        )
        
        session.commit()
        session.close()
        engine.dispose()
        
        logger.info("Default user created successfully (Local)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create default user (Local): {str(e)}")
        return False

def setup_database(use_docker=True):
    """Run complete database setup process."""
    logger.info(f"Starting database setup process using {'Docker' if use_docker else 'Local'} environment...")
    
    # Step 1: Reset database
    logger.info("Step 1: Resetting database...")
    if use_docker:
        if not reset_database_docker():
            logger.error("Database reset failed")
            return False
    else:
        if not reset_database_local():
            logger.error("Database reset failed")
            return False
        
    # Step 2: Initialize database
    logger.info("Step 2: Initializing database...")
    if use_docker:
        if not init_database_docker():
            logger.error("Database initialization failed")
            return False
    else:
        if not init_database_local():
            logger.error("Database initialization failed")
            return False
        
    # Step 3: Run migrations
    logger.info("Step 3: Running migrations...")
    if use_docker:
        if not run_migrations_docker():
            logger.error("Database migrations failed")
            return False
    else:
        if not run_migrations_local():
            logger.error("Database migrations failed")
            return False
    
    # Step 4: Create default user
    logger.info("Step 4: Creating default user...")
    if use_docker:
        if not create_default_user_docker():
            logger.error("Default user creation failed")
            return False
    else:
        if not create_default_user_local():
            logger.error("Default user creation failed")
            return False
    
    logger.info("Database setup completed successfully!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup database for AI Agentic Deals System')
    parser.add_argument('--local', action='store_true', help='Use local connection instead of Docker')
    args = parser.parse_args()
    
    success = setup_database(not args.local)
    sys.exit(0 if success else 1) 