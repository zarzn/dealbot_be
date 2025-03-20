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
from decimal import Decimal
from core.models.enums import TransactionType, TransactionStatus
from core.models.token import TokenTransaction, TokenBalance
from datetime import datetime, timezone, timedelta
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

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
        
        # Add token balance for the test user
        token_balance_id = str(uuid4())
        initial_balance = 1000.0  # Start with 1000 tokens
        
        insert_token_balance_query = f"""
        INSERT INTO token_balances (
            id, user_id, balance, created_at, updated_at
        ) VALUES (
            '{token_balance_id}', '{test_user_id}', {initial_balance}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', insert_token_balance_query],
            check=True
        )
        
        # Add a few token transactions for the test user
        for i in range(5):
            tx_id = str(uuid4())
            amount = 50.0 + (i * 10)  # Varying amounts
            tx_type = "credit" if i % 2 == 0 else "deduction"
            description = f"Test transaction #{i+1}" if tx_type == "credit" else f"Service fee #{i+1}"
            status = "completed"
            timestamp = f"CURRENT_TIMESTAMP - INTERVAL '{i} days'"
            
            insert_tx_query = f"""
            INSERT INTO token_transactions (
                id, user_id, amount, type, status, meta_data,
                created_at, updated_at, completed_at
            ) VALUES (
                '{tx_id}', '{test_user_id}', {amount}, '{tx_type}', '{status}', 
                '{{"description": "{description}", "source": "test_data"}}', 
                {timestamp}, {timestamp}, {timestamp}
            )
            """
            
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', insert_tx_query],
                check=True
            )
        
        logger.info(f"Test user created successfully with ID: {test_user_id} and initial balance of {initial_balance} tokens")
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
            # Insert Amazon market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                '363b6f97-b37f-41f2-9170-721fafa68b5e', 
                'Amazon', 
                'amazon', 
                'Amazon Marketplace Integration', 
                'active', 
                'https://api.amazon.com', 
                '{"api_key": "SAMPLE_KEY", "region": "us-east-1"}',
                TRUE,
                15,
                125,
                1000,
                0.95,
                180.5,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Walmart market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                'aadf3354-5d6e-4e83-b507-7e0871535bd1', 
                'Walmart', 
                'walmart', 
                'Walmart Marketplace Integration', 
                'active', 
                'https://api.walmart.com', 
                '{"api_key": "SAMPLE_KEY"}',
                TRUE,
                10,
                85,
                850,
                0.90,
                210.3,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Google Shopping market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                '828c2bb8-005e-458d-bd20-cd80e7a45b6d', 
                'Google Shopping', 
                'google_shopping', 
                'Google Shopping Integration', 
                'active', 
                'https://api.googleshopping.com', 
                '{"api_key": "SAMPLE_KEY", "region": "us"}',
                TRUE,
                8,
                95,
                720,
                0.88,
                195.7,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert real deals for Amazon market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                '502e7599-6006-4a5a-8946-b68713440ee1', 
                'Sony WH-1000XM4 Wireless Noise Cancelling Headphones',
                'Industry-leading noise cancellation with Dual Noise Sensor technology',
                'https://amazon.com/sony-wh1000xm4',
                'https://m.media-amazon.com/images/I/51SKmu2G9FL._AC_SX522_.jpg',
                249.99,
                348.00,
                'USD',
                'amazon',
                'electronics',
                TRUE,
                'active',
                '363b6f97-b37f-41f2-9170-721fafa68b5e',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "Sony Store", "rating": 4.8}',
                '{"in_stock": true, "quantity": 120}',
                92.5,
                '{"vendor": "Sony", "is_verified": true}',
                '{"price_history": [{"price": "348.00", "timestamp": "2023-12-15T00:00:00Z", "source": "historical"}, {"price": "299.99", "timestamp": "2023-12-25T00:00:00Z", "source": "historical"}, {"price": "249.99", "timestamp": "2024-01-05T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '5 days'
            ) ON CONFLICT DO NOTHING;
            """,
            
            # Insert real deals for Walmart market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                'a1b2c3d4-e5f6-4a5a-8946-123456789abc', 
                'iRobot Roomba i3 EVO Robot Vacuum',
                'Smart robot vacuum with Wi-Fi connectivity and personalized cleaning suggestions',
                'https://walmart.com/roomba-i3',
                'https://i5.walmartimages.com/seo/iRobot-Roomba-i3-EVO-3150-Wi-Fi-Robotic-Vacuum-Cleaner-Gray_3bced1e6-e4ad-4ad7-8889-4fa6ae1aff91.e1d1fd52ee25f4d68cff1f06d1855ebe.jpeg',
                299.00,
                399.99,
                'USD',
                'walmart',
                'home',
                TRUE,
                'active',
                'aadf3354-5d6e-4e83-b507-7e0871535bd1',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "Walmart", "rating": 4.6}',
                '{"in_stock": true, "quantity": 45}',
                88.0,
                '{"vendor": "iRobot", "is_verified": true}',
                '{"price_history": [{"price": "399.99", "timestamp": "2023-12-01T00:00:00Z", "source": "historical"}, {"price": "349.99", "timestamp": "2023-12-20T00:00:00Z", "source": "historical"}, {"price": "299.00", "timestamp": "2024-01-10T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '3 days'
            ) ON CONFLICT DO NOTHING;
            """,
            
            # Insert real deals for Google Shopping market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                'f9e8d7c6-b5a4-4a5a-8946-987654321fed', 
                'Apple MacBook Air 13.3" Laptop M1 Chip',
                'Apple M1 chip with 8-core CPU and 7-core GPU, 8GB RAM, 256GB SSD',
                'https://googleshopping.com/macbook-air-m1',
                'https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6366/6366606_sd.jpg',
                799.99,
                999.00,
                'USD',
                'google_shopping',
                'electronics',
                TRUE,
                'active',
                '828c2bb8-005e-458d-bd20-cd80e7a45b6d',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "TechDeals", "rating": 4.9}',
                '{"in_stock": true, "quantity": 12}',
                95.0,
                '{"vendor": "Apple", "is_verified": true}',
                '{"price_history": [{"price": "999.00", "timestamp": "2023-11-25T00:00:00Z", "source": "historical"}, {"price": "849.99", "timestamp": "2023-12-15T00:00:00Z", "source": "historical"}, {"price": "799.99", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '7 days'
            ) ON CONFLICT DO NOTHING;
            """
        ]
        
        for sql in sql_commands:
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', sql],
                check=True,
            )
            
        logger.info("Default markets and deals created successfully (Docker)")
        return True
    except Exception as e:
        logger.error(f"Failed to create default markets and deals (Docker): {str(e)}")
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
            # Insert Amazon market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                '363b6f97-b37f-41f2-9170-721fafa68b5e', 
                'Amazon', 
                'amazon', 
                'Amazon Marketplace Integration', 
                'active', 
                'https://api.amazon.com', 
                '{"api_key": "SAMPLE_KEY", "region": "us-east-1"}',
                TRUE,
                15,
                125,
                1000,
                0.95,
                180.5,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Walmart market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                'aadf3354-5d6e-4e83-b507-7e0871535bd1', 
                'Walmart', 
                'walmart', 
                'Walmart Marketplace Integration', 
                'active', 
                'https://api.walmart.com', 
                '{"api_key": "SAMPLE_KEY"}',
                TRUE,
                10,
                85,
                850,
                0.90,
                210.3,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert Google Shopping market with comprehensive data
            """
            INSERT INTO markets (
                id, name, type, description, status, api_endpoint, config, 
                is_active, error_count, requests_today, total_requests, 
                success_rate, avg_response_time, rate_limit, 
                created_at, updated_at
            )
            VALUES (
                '828c2bb8-005e-458d-bd20-cd80e7a45b6d', 
                'Google Shopping', 
                'google_shopping', 
                'Google Shopping Integration', 
                'active', 
                'https://api.googleshopping.com', 
                '{"api_key": "SAMPLE_KEY", "region": "us"}',
                TRUE,
                8,
                95,
                720,
                0.88,
                195.7,
                100,
                NOW(), 
                NOW()
            ) ON CONFLICT (name) DO NOTHING;
            """,
            
            # Insert real deals for Amazon market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                '502e7599-6006-4a5a-8946-b68713440ee1', 
                'Sony WH-1000XM4 Wireless Noise Cancelling Headphones',
                'Industry-leading noise cancellation with Dual Noise Sensor technology',
                'https://amazon.com/sony-wh1000xm4',
                'https://m.media-amazon.com/images/I/51SKmu2G9FL._AC_SX522_.jpg',
                249.99,
                348.00,
                'USD',
                'amazon',
                'electronics',
                TRUE,
                'active',
                '363b6f97-b37f-41f2-9170-721fafa68b5e',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "Sony Store", "rating": 4.8}',
                '{"in_stock": true, "quantity": 120}',
                92.5,
                '{"vendor": "Sony", "is_verified": true}',
                '{"price_history": [{"price": "348.00", "timestamp": "2023-12-15T00:00:00Z", "source": "historical"}, {"price": "299.99", "timestamp": "2023-12-25T00:00:00Z", "source": "historical"}, {"price": "249.99", "timestamp": "2024-01-05T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '5 days'
            ) ON CONFLICT DO NOTHING;
            """,
            
            # Insert real deals for Walmart market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                'a1b2c3d4-e5f6-4a5a-8946-123456789abc', 
                'iRobot Roomba i3 EVO Robot Vacuum',
                'Smart robot vacuum with Wi-Fi connectivity and personalized cleaning suggestions',
                'https://walmart.com/roomba-i3',
                'https://i5.walmartimages.com/seo/iRobot-Roomba-i3-EVO-3150-Wi-Fi-Robotic-Vacuum-Cleaner-Gray_3bced1e6-e4ad-4ad7-8889-4fa6ae1aff91.e1d1fd52ee25f4d68cff1f06d1855ebe.jpeg',
                299.00,
                399.99,
                'USD',
                'walmart',
                'home',
                TRUE,
                'active',
                'aadf3354-5d6e-4e83-b507-7e0871535bd1',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "Walmart", "rating": 4.6}',
                '{"in_stock": true, "quantity": 45}',
                88.0,
                '{"vendor": "iRobot", "is_verified": true}',
                '{"price_history": [{"price": "399.99", "timestamp": "2023-12-01T00:00:00Z", "source": "historical"}, {"price": "349.99", "timestamp": "2023-12-20T00:00:00Z", "source": "historical"}, {"price": "299.00", "timestamp": "2024-01-10T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '3 days'
            ) ON CONFLICT DO NOTHING;
            """,
            
            # Insert real deals for Google Shopping market
            """
            INSERT INTO deals (
                id, title, description, url, image_url, price, original_price, 
                currency, source, category, 
                is_active, status, market_id, user_id,
                seller_info, availability, score, deal_metadata, price_metadata,
                created_at, updated_at, found_at
            )
            VALUES (
                'f9e8d7c6-b5a4-4a5a-8946-987654321fed', 
                'Apple MacBook Air 13.3" Laptop M1 Chip',
                'Apple M1 chip with 8-core CPU and 7-core GPU, 8GB RAM, 256GB SSD',
                'https://googleshopping.com/macbook-air-m1',
                'https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6366/6366606_sd.jpg',
                799.99,
                999.00,
                'USD',
                'google_shopping',
                'electronics',
                TRUE,
                'active',
                '828c2bb8-005e-458d-bd20-cd80e7a45b6d',
                '00000000-0000-4000-a000-000000000001',
                '{"name": "TechDeals", "rating": 4.9}',
                '{"in_stock": true, "quantity": 12}',
                95.0,
                '{"vendor": "Apple", "is_verified": true}',
                '{"price_history": [{"price": "999.00", "timestamp": "2023-11-25T00:00:00Z", "source": "historical"}, {"price": "849.99", "timestamp": "2023-12-15T00:00:00Z", "source": "historical"}, {"price": "799.99", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}]}',
                NOW(),
                NOW(),
                NOW() - INTERVAL '7 days'
            ) ON CONFLICT DO NOTHING;
            """
        ]
        
        # Execute each SQL command
        for sql in sql_commands:
            conn.execute(text(sql))
            
        # Commit the transaction
        conn.execute(text("COMMIT"))
        conn.close()
        
        logger.info("Default markets and deals created successfully (Local)")
        return True
    except Exception as e:
        logger.error(f"Failed to create default markets and deals (Local): {str(e)}")
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

def add_initial_tokens_docker():
    """Add initial tokens to test user in Docker environment."""
    try:
        # Check if test user exists and get the ID
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM users WHERE email = 'test@test.com'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If no test user, skip token addition
        if "0 rows" in result.stdout:
            logger.info("Test user does not exist, skipping token addition (Docker)")
            return True
        
        # Extract user ID from the result
        lines = result.stdout.strip().split('\n')
        if len(lines) < 4:  # Header + separator + data + row count
            logger.error("Could not parse user ID from database query result")
            return False
        
        user_id = lines[2].strip()
        logger.info(f"User found with ID: {user_id}, ensuring token transactions exist")
        
        # Check if user already has transactions
        tx_result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             f"SELECT COUNT(*) FROM token_transactions WHERE user_id = '{user_id}'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Extract transaction count
        try:
            tx_lines = tx_result.stdout.strip().split('\n')
            if len(tx_lines) < 4:
                tx_count = 0
            else:
                tx_count = int(tx_lines[2].strip())
                
            if tx_count > 0:
                logger.info(f"User already has {tx_count} token transactions, skipping additional creation")
                return True
                
        except Exception as count_err:
            logger.error(f"Error parsing transaction count: {str(count_err)}")
            # Continue anyway to try to add transactions
        
        # Current timestamp for all records
        timestamp = "NOW()"
        
        # Standard token amount
        token_amount = 1000.0
        
        # Check if user has token balance but no transactions - add a main transaction
        try:
            transaction_query = f"""
            INSERT INTO token_transactions (
                id, user_id, amount, type, status, meta_data,
                created_at, updated_at, completed_at
            ) VALUES (
                '{str(uuid4())}', '{user_id}', {token_amount}, 'credit', 'completed', 
                '{{"description": "Initial balance allocation", "source": "system"}}', 
                {timestamp}, {timestamp}, {timestamp}
            )
            """
            
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
                transaction_query],
                check=True
            )
            logger.info(f"Created initial transaction record for {token_amount} tokens")
            
            # Add a few more transactions for history
            for i in range(3):
                tx_id = str(uuid4())
                amount = 25.0 + (i * 15)  # Different amounts than the ones in create_test_user
                tx_type = "credit" if i % 2 == 0 else "deduction"
                reason = f"Sample {tx_type} transaction #{i+1}"
                past_timestamp = f"NOW() - INTERVAL '{i+7} days'"
                
                sample_tx_query = f"""
                INSERT INTO token_transactions (
                    id, user_id, amount, type, status, meta_data,
                    created_at, updated_at, completed_at
                ) VALUES (
                    '{tx_id}', '{user_id}', {amount}, '{tx_type}', 'completed', 
                    '{{"description": "{reason}", "source": "system"}}', 
                    {past_timestamp}, {past_timestamp}, {past_timestamp}
                )
                """
                
                subprocess.run(
                    ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
                    sample_tx_query],
                    check=True
                )
                logger.info(f"Created additional sample transaction: {reason}")
                
        except Exception as tx_error:
            logger.error(f"Failed to create transaction record(s): {str(tx_error)}")
            # Continue execution even if transaction record creation fails
        
        return True
    except Exception as e:
        logger.error(f"Failed to add initial tokens (Docker): {str(e)}")
        return False

def add_initial_tokens_local():
    """Add initial tokens to test user in local environment."""
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
        
        # Check if test user exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'test@test.com'"))
        test_user = result.fetchone()
        
        if not test_user:
            logger.info("Test user does not exist, skipping token addition (Local)")
            session.close()
            engine.dispose()
            return True
        
        user_id = test_user[0]
        logger.info(f"Adding tokens to test user with ID: {user_id}")
        
        # Check if user already has a balance record
        balance_result = session.execute(
            text(f"SELECT id FROM token_balances WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        balance = balance_result.fetchone()
        
        current_time = datetime.now(timezone.utc)
        
        if not balance:
            # Create balance record if it doesn't exist
            session.execute(
                text("""
                INSERT INTO token_balances (user_id, balance, updated_at, created_at)
                VALUES (:user_id, :balance, :timestamp, :timestamp)
                """),
                {
                    "user_id": user_id,
                    "balance": 100.0,
                    "timestamp": current_time
                }
            )
            logger.info(f"Created balance record for test user with 100 tokens")
        else:
            # Update balance if it exists
            session.execute(
                text("""
                UPDATE token_balances 
                SET balance = :balance, updated_at = :timestamp
                WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                    "balance": 100.0,
                    "timestamp": current_time
                }
            )
            logger.info(f"Updated balance for test user to 100 tokens")
        
        # Create a transaction record for the initial tokens
        session.execute(
            text("""
            INSERT INTO token_transactions (
                user_id, type, amount, status, meta_data, created_at
            ) VALUES (
                :user_id, :transaction_type, :amount, :status, :meta_data, :timestamp
            )
            """),
            {
                "user_id": user_id,
                "transaction_type": TransactionType.REWARD.value,
                "amount": 100.0,
                "status": TransactionStatus.COMPLETED.value,
                "meta_data": {"reason": "Initial token allocation"},
                "timestamp": current_time
            }
        )
        logger.info(f"Created transaction record for initial token allocation")
        
        session.commit()
        session.close()
        engine.dispose()
        return True
    except Exception as e:
        logger.error(f"Failed to add initial tokens (Local): {str(e)}")
        return False

def create_test_goals_docker():
    """Create test goals for the test user in Docker environment."""
    try:
        # Check if test user exists and get the ID
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM users WHERE email = 'test@test.com'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If no test user, skip goal creation
        if "0 rows" in result.stdout:
            logger.info("Test user does not exist, skipping goal creation (Docker)")
            return True
        
        # Extract user ID from the result
        lines = result.stdout.strip().split('\n')
        if len(lines) < 4:  # Header + separator + data + row count
            logger.error("Could not parse user ID from database query result")
            return False
        
        user_id = lines[2].strip()
        logger.info(f"Creating test goals for user with ID: {user_id}")
        
        # Define constraints for sample goals
        constraints_electronics = {
            "price_range": {"min": 100, "max": 1000},
            "brands": ["Samsung", "Apple", "Sony"],
            "condition": "new",
            "max_shipping_days": 7
        }
        
        constraints_clothing = {
            "price_range": {"min": 20, "max": 200},
            "sizes": ["M", "L"],
            "gender": "unisex",
            "categories": ["casual", "sportswear"]
        }
        
        # Create test goals
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             f"""
             INSERT INTO goals (
                 id, user_id, item_category, title, description, constraints, 
                 deadline, status, priority, max_matches, max_tokens, notification_threshold,
                 auto_buy_threshold, created_at, updated_at
             ) VALUES (
                 '{str(uuid.uuid4())}', '{user_id}', 'electronics', 'Find a good laptop deal', 
                 'Looking for a laptop with at least 16GB RAM and 512GB SSD',
                 '{json.dumps(constraints_electronics)}', 
                 NOW() + INTERVAL '30 days', 'active', 'medium', 5, 100.0, 0.8, 0.95,
                 NOW(), NOW()
             )
             """],
            check=True
        )
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             f"""
             INSERT INTO goals (
                 id, user_id, item_category, title, description, constraints, 
                 deadline, status, priority, max_matches, max_tokens, notification_threshold,
                 auto_buy_threshold, created_at, updated_at
             ) VALUES (
                 '{str(uuid.uuid4())}', '{user_id}', 'fashion', 'Find running shoes', 
                 'Looking for comfortable running shoes',
                 '{json.dumps(constraints_clothing)}', 
                 NOW() + INTERVAL '15 days', 'active', 'high', 3, 50.0, 0.7, 0.9,
                 NOW(), NOW()
             )
             """],
            check=True
        )
        
        logger.info("Test goals created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create test goals (Docker): {str(e)}")
        return False

def create_test_goals_local():
    """Create test goals for the test user in local environment."""
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
        
        # Check if test user exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'test@test.com'"))
        test_user = result.fetchone()
        
        if not test_user:
            logger.info("Test user does not exist, skipping goal creation (Local)")
            session.close()
            engine.dispose()
            return True
        
        user_id = test_user[0]
        logger.info(f"Creating test goals for user with ID: {user_id}")
        
        # Define constraints for sample goals
        constraints_electronics = {
            "price_range": {"min": 100, "max": 1000},
            "brands": ["Samsung", "Apple", "Sony"],
            "condition": "new",
            "max_shipping_days": 7
        }
        
        constraints_clothing = {
            "price_range": {"min": 20, "max": 200},
            "sizes": ["M", "L"],
            "gender": "unisex",
            "categories": ["casual", "sportswear"]
        }
        
        # Create test goals
        session.execute(
            text("""
            INSERT INTO goals (
                id, user_id, item_category, title, description, constraints, 
                deadline, status, priority, max_matches, max_tokens, notification_threshold,
                auto_buy_threshold, created_at, updated_at
            ) VALUES (
                :id, :user_id, :item_category, :title, :description, :constraints, 
                :deadline, :status, :priority, :max_matches, :max_tokens, :notification_threshold,
                :auto_buy_threshold, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """),
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "item_category": "electronics",
                "title": "Find a good laptop deal",
                "description": "Looking for a laptop with at least 16GB RAM and 512GB SSD",
                "constraints": json.dumps(constraints_electronics),
                "deadline": datetime.now(timezone.utc) + timedelta(days=30),
                "status": "active",
                "priority": "medium",
                "max_matches": 5,
                "max_tokens": 100.0,
                "notification_threshold": 0.8,
                "auto_buy_threshold": 0.95
            }
        )
        
        session.execute(
            text("""
            INSERT INTO goals (
                id, user_id, item_category, title, description, constraints, 
                deadline, status, priority, max_matches, max_tokens, notification_threshold,
                auto_buy_threshold, created_at, updated_at
            ) VALUES (
                :id, :user_id, :item_category, :title, :description, :constraints, 
                :deadline, :status, :priority, :max_matches, :max_tokens, :notification_threshold,
                :auto_buy_threshold, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """),
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "item_category": "fashion",
                "title": "Find running shoes",
                "description": "Looking for comfortable running shoes",
                "constraints": json.dumps(constraints_clothing),
                "deadline": datetime.now(timezone.utc) + timedelta(days=15),
                "status": "active",
                "priority": "high",
                "max_matches": 3,
                "max_tokens": 50.0,
                "notification_threshold": 0.7,
                "auto_buy_threshold": 0.9
            }
        )
        
        session.commit()
        session.close()
        engine.dispose()
        logger.info("Test goals created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create test goals (Local): {str(e)}")
        return False

def create_test_deals_docker():
    """Create test deals for the test user in Docker environment."""
    try:
        # Check if test user exists
        result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM users WHERE email = 'test@test.com'"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "0 rows" in result.stdout:
            logger.info("Test user does not exist, skipping test deals creation (Docker)")
            return True
        
        # Extract user ID from the result
        lines = result.stdout.strip().split('\n')
        if len(lines) < 4:
            logger.error("Could not parse user ID from database query result")
            return False
        
        user_id = lines[2].strip()
        logger.info(f"Creating test deals for user with ID: {user_id}")
        
        # Check if there's a market we can use
        market_result = subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             "SELECT id FROM markets LIMIT 1"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If no market exists, create one
        if "0 rows" in market_result.stdout:
            logger.info("No markets found, creating a test market")
            market_id = str(uuid.uuid4())
            subprocess.run(
                ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
                 f"""
                 INSERT INTO markets (
                     id, name, type, description, status, api_endpoint, config, 
                     is_active, created_at, updated_at
                 ) VALUES (
                     '{market_id}', 'Test Market', 'test', 'Test Market for Deals', 'active', 
                     'https://api.testmarket.com', '{{}}', true, NOW(), NOW()
                 )
                 """],
                check=True
            )
        else:
            # Extract market ID from the result
            market_lines = market_result.stdout.strip().split('\n')
            if len(market_lines) < 4:
                logger.error("Could not parse market ID from database query result")
                return False
            
            market_id = market_lines[2].strip()
        
        logger.info(f"Using market ID: {market_id}")
        
        # Create test deals
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             f"""
             INSERT INTO deals (
                 id, user_id, market_id, title, description, url, image_url, 
                 price, original_price, currency, source, category, 
                 status, is_active, seller_info, availability, score,
                 deal_metadata, price_metadata, created_at, updated_at, found_at
             ) VALUES (
                 '{str(uuid.uuid4())}', '{user_id}', '{market_id}', 'Gaming Laptop for Sale', 
                 'High-performance gaming laptop with RTX 3080', 'https://testmarket.com/deals/gaming-laptop',
                 'https://example.com/images/laptop.jpg',
                 1200.00, 1500.00, 'USD', 'manual', 'electronics',
                 'active', TRUE, 
                 '{{"name": "Test Seller", "rating": 4.7}}',
                 '{{"in_stock": true, "quantity": 50}}',
                 90.5,
                 '{{"vendor": "ASUS", "is_verified": true}}',
                 '{{"price_history": [{{"price": "1500.00", "timestamp": "2023-11-01T00:00:00Z", "source": "historical"}}, {{"price": "1200.00", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}}]}}',
                 NOW(), NOW(), NOW() - INTERVAL '2 days'
             )
             """],
            check=True
        )
        
        subprocess.run(
            ['docker', 'exec', 'deals_postgres', 'psql', '-U', 'postgres', '-d', 'agentic_deals', '-c', 
             f"""
             INSERT INTO deals (
                 id, user_id, market_id, title, description, url, image_url, 
                 price, original_price, currency, source, category, 
                 status, is_active, seller_info, availability, score,
                 deal_metadata, price_metadata, created_at, updated_at, found_at
             ) VALUES (
                 '{str(uuid.uuid4())}', '{user_id}', '{market_id}', 'Wireless Headphones', 
                 'Noise-cancelling wireless headphones', 'https://testmarket.com/deals/headphones',
                 'https://example.com/images/headphones.jpg',
                 200.00, 250.00, 'USD', 'manual', 'electronics',
                 'active', TRUE, 
                 '{{"name": "Audio Shop", "rating": 4.5}}',
                 '{{"in_stock": true, "quantity": 25}}',
                 85.0,
                 '{{"vendor": "Sony", "is_verified": true}}',
                 '{{"price_history": [{{"price": "250.00", "timestamp": "2023-12-01T00:00:00Z", "source": "historical"}}, {{"price": "200.00", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}}]}}',
                 NOW(), NOW(), NOW() - INTERVAL '1 day'
             )
             """],
            check=True
        )
        
        logger.info("Test deals created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create test deals (Docker): {str(e)}")
        return False

def create_test_deals_local():
    """Create test deals for the test user in local environment."""
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
        
        # Check if test user exists
        result = session.execute(text("SELECT id FROM users WHERE email = 'test@test.com'"))
        test_user = result.fetchone()
        
        if not test_user:
            logger.info("Test user does not exist, skipping test deals creation (Local)")
            session.close()
            engine.dispose()
            return True
        
        user_id = test_user[0]
        logger.info(f"Creating test deals for user with ID: {user_id}")
        
        # Get a market ID
        market_result = session.execute(text("SELECT id FROM markets LIMIT 1"))
        market = market_result.fetchone()
        
        if not market:
            logger.info("No markets found, creating a test market")
            market_id = str(uuid.uuid4())
            session.execute(
                text("""
                INSERT INTO markets (
                    id, name, type, description, status, api_endpoint, config,
                    is_active, created_at, updated_at
                ) VALUES (
                    :id, :name, :type, :description, :status, :api_endpoint, :config,
                    :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """),
                {
                    "id": market_id,
                    "name": "Test Market",
                    "type": "test",
                    "description": "Test Market for Deals",
                    "status": "active",
                    "api_endpoint": "https://api.testmarket.com",
                    "config": "{}",
                    "is_active": True
                }
            )
        else:
            market_id = market[0]
        
        logger.info(f"Using market ID: {market_id}")
        
        # Create test deals
        session.execute(
            text("""
            INSERT INTO deals (
                id, user_id, market_id, title, description, url, image_url, 
                price, original_price, currency, source, category, 
                status, is_active, seller_info, availability, score,
                deal_metadata, price_metadata, created_at, updated_at, found_at
            ) VALUES (
                :id, :user_id, :market_id, :title, :description, :url, :image_url, 
                :price, :original_price, :currency, :source, :category, 
                :status, :is_active, :seller_info, :availability, :score,
                :deal_metadata, :price_metadata, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :found_at
            )
            """),
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "market_id": market_id,
                "title": "Gaming Laptop for Sale",
                "description": "High-performance gaming laptop with RTX 3080",
                "url": "https://testmarket.com/deals/gaming-laptop",
                "image_url": "https://example.com/images/laptop.jpg",
                "price": 1200.00,
                "original_price": 1500.00,
                "currency": "USD",
                "source": "manual",
                "category": "electronics",
                "status": "active",
                "is_active": True,
                "seller_info": json.dumps({"name": "Test Seller", "rating": 4.7}),
                "availability": json.dumps({"in_stock": True, "quantity": 50}),
                "score": 90.5,
                "deal_metadata": json.dumps({"vendor": "ASUS", "is_verified": True}),
                "price_metadata": json.dumps({"price_history": [{"price": "1500.00", "timestamp": "2023-11-01T00:00:00Z", "source": "historical"}, {"price": "1200.00", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}]}),
                "found_at": datetime.now() - timedelta(days=2)
            }
        )
        
        session.execute(
            text("""
            INSERT INTO deals (
                id, user_id, market_id, title, description, url, image_url, 
                price, original_price, currency, source, category, 
                status, is_active, seller_info, availability, score,
                deal_metadata, price_metadata, created_at, updated_at, found_at
            ) VALUES (
                :id, :user_id, :market_id, :title, :description, :url, :image_url, 
                :price, :original_price, :currency, :source, :category, 
                :status, :is_active, :seller_info, :availability, :score,
                :deal_metadata, :price_metadata, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :found_at
            )
            """),
            {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "market_id": market_id,
                "title": "Wireless Headphones",
                "description": "Noise-cancelling wireless headphones",
                "url": "https://testmarket.com/deals/headphones",
                "image_url": "https://example.com/images/headphones.jpg",
                "price": 200.00,
                "original_price": 250.00,
                "currency": "USD",
                "source": "manual",
                "category": "electronics",
                "status": "active",
                "is_active": True,
                "seller_info": json.dumps({"name": "Audio Shop", "rating": 4.5}),
                "availability": json.dumps({"in_stock": True, "quantity": 25}),
                "score": 85.0,
                "deal_metadata": json.dumps({"vendor": "Sony", "is_verified": True}),
                "price_metadata": json.dumps({"price_history": [{"price": "250.00", "timestamp": "2023-12-01T00:00:00Z", "source": "historical"}, {"price": "200.00", "timestamp": "2024-01-01T00:00:00Z", "source": "current"}]}),
                "found_at": datetime.now() - timedelta(days=1)
            }
        )
        
        session.commit()
        session.close()
        engine.dispose()
        logger.info("Test deals created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create test deals (Local): {str(e)}")
        return False

def setup_database(use_docker=None):
    """Run complete database setup process."""
    # If use_docker is not specified, auto-detect the environment
    if use_docker is None:
        use_docker = determine_environment()
    
    env = "docker" if use_docker else "local"
    logger.info(f"Starting database setup process using {env} environment...")
    
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
    
    # Step 5: Add initial tokens to test user
    logger.info("Step 5: Adding initial tokens to test user...")
    if use_docker:
        if not add_initial_tokens_docker():
            logger.error("Initial token allocation failed")
            return False
    else:
        if not add_initial_tokens_local():
            logger.error("Initial token allocation failed")
            return False
    
    # Step 6: Create default markets
    logger.info("Step 6: Creating default markets...")
    if use_docker:
        if not create_default_markets_docker():
            logger.error("Default markets creation failed")
            return False
    else:
        if not create_default_markets_local():
            logger.error("Default markets creation failed")
            return False
    
    # Step 7: Create test goals
    logger.info("Step 7: Creating test goals...")
    if use_docker:
        if not create_test_goals_docker():
            logger.error("Test goals creation failed")
            return False
    else:
        if not create_test_goals_local():
            logger.error("Test goals creation failed")
            return False
    
    # Step 8: Create test deals
    logger.info("Step 8: Creating test deals...")
    if use_docker:
        if not create_test_deals_docker():
            logger.error("Test deals creation failed")
            return False
    else:
        if not create_test_deals_local():
            logger.error("Test deals creation failed")
            return False
    
    logger.info("Database setup completed successfully!")
    return True

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Setup the database for the AI Agentic Deals System')
    parser.add_argument('--docker', action='store_true', help='Force Docker environment')
    parser.add_argument('--local', action='store_true', help='Force local environment')
    args = parser.parse_args()
    
    # Determine environment
    use_docker = None
    if args.docker:
        use_docker = True
    elif args.local:
        use_docker = False
    
    success = setup_database(use_docker)
    sys.exit(0 if success else 1) 