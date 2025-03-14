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
import json

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
             "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname IN ('agentic_deals', 'agentic_deals_test') AND pid <> pg_backend_pid()"],
            check=True
        )
        
        # Drop and recreate databases
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "DROP DATABASE IF EXISTS agentic_deals"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "DROP DATABASE IF EXISTS agentic_deals_test"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "CREATE DATABASE agentic_deals"],
            check=True
        )
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-c', 
             "CREATE DATABASE agentic_deals_test"],
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
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_port = os.environ.get('DB_PORT', '5432')
        
        logger.info(f"Connecting to database at {db_host}:{db_port} as {db_user}")
        engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres')
        conn = engine.connect()
        conn.execute(text("COMMIT"))  # Close any open transactions
        
        # Drop connections to deals database
        conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname IN ('agentic_deals', 'agentic_deals_test')
            AND pid <> pg_backend_pid()
        """))
        
        # Drop and recreate databases
        conn.execute(text("DROP DATABASE IF EXISTS agentic_deals"))
        conn.execute(text("DROP DATABASE IF EXISTS agentic_deals_test"))
        conn.execute(text("CREATE DATABASE agentic_deals"))
        conn.execute(text("CREATE DATABASE agentic_deals_test"))
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
        for db_name in ['agentic_deals', 'agentic_deals_test']:
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
        # Get database connection parameters from environment variables
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_port = os.environ.get('DB_PORT', '5432')
        
        # Initialize both main and test databases
        for db_name in ['agentic_deals', 'agentic_deals_test']:
            # Connect to database
            connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
            logger.info(f"Connecting to {db_name} at {db_host}:{db_port}")
            engine = create_engine(connection_string)
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
        for db_name in ['agentic_deals', 'agentic_deals_test']:
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
        
        # Get database connection parameters from environment variables
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_port = os.environ.get('DB_PORT', '5432')
        
        # Get the parent directory (backend) where alembic.ini is located
        backend_dir = current_dir
        if "backend" not in current_dir:
            backend_dir = os.path.join(current_dir, "backend")
        
        # Run migrations for both main and test databases
        for db_name in ['agentic_deals', 'agentic_deals_test']:
            # Set the database URL in environment
            os.environ['DATABASE_URL'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
            logger.info(f"Setting DATABASE_URL to: {os.environ['DATABASE_URL']}")
            
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
    """Create a default system admin user in the database using Docker."""
    try:
        # Use docker exec to run SQL commands in the postgres container
        # First check if user already exists
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM users WHERE email = 'admin@system.local'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If user exists, skip creation
        if "0 rows" not in result.stdout:
            logger.info("System admin user already exists, skipping creation (Docker)")
            return True
        
        # Create system admin user with a strong password and a consistent UUID for system operations
        # Using a fixed UUID for system user to ensure consistency across environments
        system_user_id = "00000000-0000-4000-a000-000000000001"
        hashed_password = get_password_hash("Adm1n$yst3m#S3cur3P@ss!")
        
        # Insert user into database
        insert_query = f"""
        INSERT INTO users (
            id, email, name, password, status, preferences, notification_channels,
            email_verified, created_at, updated_at
        ) VALUES (
            '{system_user_id}', 'admin@system.local', 'System Admin', '{hashed_password}', 'active', '{{}}', '[]',
            TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', insert_query],
            check=True
        )
        
        logger.info(f"System admin user created successfully with ID: {system_user_id}")
        
        # Also create a regular test user for convenience if needed
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM users WHERE email = 'test@test.com'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "0 rows" not in result.stdout:
            logger.info("Test user already exists, skipping creation (Docker)")
            return True
            
        test_user_id = str(uuid4())
        test_password = get_password_hash("Qwerty123!")
        
        insert_test_query = f"""
        INSERT INTO users (
            id, email, name, password, status, preferences, notification_channels,
            email_verified, created_at, updated_at
        ) VALUES (
            '{test_user_id}', 'test@test.com', 'Test User', '{test_password}', 'active', '{{}}', '[]',
            TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', insert_test_query],
            check=True
        )
        
        logger.info(f"Test user created successfully with ID: {test_user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create users (Docker): {str(e)}")
        return False

def create_default_user_local():
    """Create a default system admin user in the database using local connection."""
    try:
        # Get database connection parameters from environment variables
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_port = os.environ.get('DB_PORT', '5432')
        
        # Connect to the database
        connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/agentic_deals'
        logger.info(f"Connecting to agentic_deals database at {db_host}:{db_port}")
        engine = create_engine(connection_string)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if system admin user already exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'admin@system.local'"))
        admin_user = result.fetchone()
        
        if not admin_user:
            # Create system admin user with a strong password and a consistent UUID for system operations
            system_user_id = "00000000-0000-4000-a000-000000000001"
            hashed_password = get_password_hash("Adm1n$yst3m#S3cur3P@ss!")
            
            # Insert system admin user into database
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
                    "id": system_user_id,
                    "email": "admin@system.local",
                    "name": "System Admin",
                    "password": hashed_password,
                    "status": "active",
                    "preferences": "{}",
                    "notification_channels": "[]",
                    "email_verified": True
                }
            )
            session.commit()
            logger.info(f"System admin user created successfully with ID: {system_user_id}")
        else:
            logger.info("System admin user already exists, skipping creation (Local)")
        
        # Check if test user already exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'test@test.com'"))
        test_user = result.fetchone()
        
        if not test_user:
            # Create a regular test user for convenience
            test_user_id = str(uuid4())
            test_password = get_password_hash("Qwerty123!")
            
            # Insert test user into database
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
                    "id": test_user_id,
                    "email": "test@test.com",
                    "name": "Test User",
                    "password": test_password,
                    "status": "active",
                    "preferences": "{}",
                    "notification_channels": "[]",
                    "email_verified": True
                }
            )
            session.commit()
            logger.info(f"Test user created successfully with ID: {test_user_id}")
        else:
            logger.info("Test user already exists, skipping creation (Local)")
        
        session.close()
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create users (Local): {str(e)}")
        return False

def create_default_markets_docker():
    """Create default markets data for Docker environment."""
    try:
        sql_commands = [
            # Insert Amazon market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'Amazon', 
                'amazon', 
                'Amazon Marketplace Integration', 
                'active', 
                'https://api.amazon.com', 
                '{"api_key": "DEMO_KEY", "region": "us-east-1", "throttle_rate": 60}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Walmart market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'Walmart', 
                'walmart', 
                'Walmart Marketplace Integration', 
                'active', 
                'https://api.walmart.com', 
                '{"api_key": "DEMO_KEY", "throttle_rate": 50}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert eBay market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'eBay', 
                'ebay', 
                'eBay Marketplace Integration', 
                'active', 
                'https://api.ebay.com', 
                '{"api_key": "DEMO_KEY", "sandbox": true}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Create sample deals - using hardcoded system user ID
            """
            INSERT INTO deals (id, title, description, url, price, currency, market_id, created_at, updated_at, status, user_id)
            SELECT 
                gen_random_uuid(), 
                'Sample Electronics Deal', 
                'Great deal on electronics item', 
                'https://amazon.com/sample1', 
                99.99, 
                'USD', 
                id, 
                NOW(), 
                NOW(),
                'active',
                '00000000-0000-4000-a000-000000000001'
            FROM markets WHERE name = 'Amazon'
            ON CONFLICT DO NOTHING;
            """,
            
            """
            INSERT INTO deals (id, title, description, url, price, currency, market_id, created_at, updated_at, status, user_id)
            SELECT 
                gen_random_uuid(), 
                'Walmart Special Offer', 
                'Limited time offer from Walmart', 
                'https://walmart.com/sample1', 
                49.99, 
                'USD', 
                id, 
                NOW(), 
                NOW(),
                'active',
                '00000000-0000-4000-a000-000000000001'
            FROM markets WHERE name = 'Walmart'
            ON CONFLICT DO NOTHING;
            """
        ]
        
        for sql in sql_commands:
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', sql],
                check=True,
            )
            
        logger.info("Default markets created successfully (Docker)")
        return True
    except Exception as e:
        logger.error(f"Failed to create default markets (Docker): {str(e)}")
        return False

def create_default_markets_local():
    """Create default markets data for local environment."""
    try:
        # Get database connection parameters from environment variables
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_password = os.environ.get('DB_PASSWORD', '12345678')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_port = os.environ.get('DB_PORT', '5432')
        
        # Connect to database
        connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/agentic_deals'
        engine = create_engine(connection_string)
        conn = engine.connect()
        
        # SQL commands to insert default market data
        sql_commands = [
            # Insert Amazon market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'Amazon', 
                'amazon', 
                'Amazon Marketplace Integration', 
                'active', 
                'https://api.amazon.com', 
                '{"api_key": "DEMO_KEY", "region": "us-east-1", "throttle_rate": 60}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Walmart market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'Walmart', 
                'walmart', 
                'Walmart Marketplace Integration', 
                'active', 
                'https://api.walmart.com', 
                '{"api_key": "DEMO_KEY", "throttle_rate": 50}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert eBay market
            """
            INSERT INTO markets (id, name, type, description, status, api_endpoint, config, created_at, updated_at)
            VALUES (
                gen_random_uuid(), 
                'eBay', 
                'ebay', 
                'eBay Marketplace Integration', 
                'active', 
                'https://api.ebay.com', 
                '{"api_key": "DEMO_KEY", "sandbox": true}',
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Create sample deals - using hardcoded system user ID
            """
            INSERT INTO deals (id, title, description, url, price, currency, market_id, created_at, updated_at, status, user_id)
            SELECT 
                gen_random_uuid(), 
                'Sample Electronics Deal', 
                'Great deal on electronics item', 
                'https://amazon.com/sample1', 
                99.99, 
                'USD', 
                id, 
                NOW(), 
                NOW(),
                'active',
                '00000000-0000-4000-a000-000000000001'
            FROM markets WHERE name = 'Amazon'
            ON CONFLICT DO NOTHING;
            """,
            
            """
            INSERT INTO deals (id, title, description, url, price, currency, market_id, created_at, updated_at, status, user_id)
            SELECT 
                gen_random_uuid(), 
                'Walmart Special Offer', 
                'Limited time offer from Walmart', 
                'https://walmart.com/sample1', 
                49.99, 
                'USD', 
                id, 
                NOW(), 
                NOW(),
                'active',
                '00000000-0000-4000-a000-000000000001'
            FROM markets WHERE name = 'Walmart'
            ON CONFLICT DO NOTHING;
            """
        ]
        
        for sql in sql_commands:
            conn.execute(text(sql))
            
        conn.execute(text("COMMIT"))
        
        logger.info("Default markets created successfully (Local)")
        conn.close()
        engine.dispose()
        return True
    except Exception as e:
        logger.error(f"Failed to create default markets (Local): {str(e)}")
        return False

def determine_environment():
    """Determine whether to use Docker or local environment based on environment variables."""
    # Check if DB_HOST environment variable is set
    db_host = os.environ.get('DB_HOST', None)
    
    # If DB_HOST is explicitly set to 'localhost', use local
    if db_host == 'localhost':
        logger.info("DB_HOST is set to 'localhost', using local environment")
        return False
    
    # If DB_HOST is explicitly set to 'deals_postgres', use Docker
    if db_host == 'deals_postgres':
        logger.info("DB_HOST is set to 'deals_postgres', using Docker environment")
        return True
    
    # Otherwise, try to detect Docker environment by checking if we can access the Docker container
    try:
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'echo', 'Docker environment detected'],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception if command fails
        )
        if result.returncode == 0:
            logger.info("Docker container 'deals_postgres' is accessible, using Docker environment")
            return True
    except Exception:
        pass
    
    # Default to local if Docker is not detected
    logger.info("Using local environment by default (Docker container not detected)")
    return False

def setup_database(use_docker=None):
    """Run complete database setup process."""
    # If use_docker is not specified, auto-detect the environment
    if use_docker is None:
        use_docker = determine_environment()
    
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
    
    # Step 5: Create default markets
    logger.info("Step 5: Creating default markets...")
    if use_docker:
        if not create_default_markets_docker():
            logger.error("Default markets creation failed")
            return False
    else:
        if not create_default_markets_local():
            logger.error("Default markets creation failed")
            return False
    
    logger.info("Database setup completed successfully")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup database for AI Agentic Deals System')
    parser.add_argument('--local', action='store_true', help='Force using local connection')
    parser.add_argument('--docker', action='store_true', help='Force using Docker connection')
    args = parser.parse_args()
    
    # Determine environment based on args
    use_docker = None
    if args.local:
        use_docker = False
    elif args.docker:
        use_docker = True
    
    success = setup_database(use_docker)
    sys.exit(0 if success else 1) 