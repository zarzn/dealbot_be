"""Script to create initial data in the database.

This script creates a default user account and other essential data needed for the
AI Agentic Deals System to function properly.
"""

import logging
import asyncio
import sys
from uuid import uuid4
import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

async def create_default_user():
    """Create system admin and test users if they don't exist."""
    try:
        # Import database module
        from core.database import get_async_db_session
        
        # Get database session
        logger.info("Connecting to database...")
        session = await get_async_db_session()
        
        try:
            # Check if system admin user already exists
            logger.info("Checking if system admin user exists...")
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": "admin@system.local"}
            )
            admin_user = result.fetchone()
            
            if not admin_user:
                # Create system admin user with a strong password and consistent UUID
                logger.info("Creating system admin user...")
                system_user_id = "00000000-0000-4000-a000-000000000001"
                admin_password = get_password_hash("Adm1n$yst3m#S3cur3P@ss!")
                
                # Insert admin user directly with SQL
                await session.execute(
                    text("""
                    INSERT INTO users (
                        id, email, name, password, status, 
                        preferences, notification_channels,
                        email_verified, created_at, updated_at
                    ) VALUES (
                        :id, :email, :name, :password, :status,
                        :preferences, :notification_channels,
                        :email_verified, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": system_user_id,
                        "email": "admin@system.local",
                        "name": "System Admin",
                        "password": admin_password,
                        "status": "active",
                        "preferences": "{}",
                        "notification_channels": "[]",
                        "email_verified": True
                    }
                )
                
                await session.commit()
                logger.info(f"System admin user created successfully with ID: {system_user_id}")
            else:
                logger.info("System admin user already exists, skipping creation")
            
            # Check if test user already exists
            logger.info("Checking if test user exists...")
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": "test@test.com"}
            )
            test_user = result.fetchone()
            
            if not test_user:
                # Create test user 
                logger.info("Creating test user...")
                test_user_id = str(uuid4())
                test_password = get_password_hash("Qwerty123!")
                
                # Insert test user directly with SQL
                await session.execute(
                    text("""
                    INSERT INTO users (
                        id, email, name, password, status, 
                        preferences, notification_channels,
                        email_verified, created_at, updated_at
                    ) VALUES (
                        :id, :email, :name, :password, :status,
                        :preferences, :notification_channels,
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
                
                await session.commit()
                logger.info(f"Test user created successfully with ID: {test_user_id}")
            else:
                logger.info("Test user already exists, skipping creation")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating users: {str(e)}")
            await session.rollback()
            return False
        finally:
            # Ensure the session is closed properly
            await session.close()
            
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return False

async def create_default_markets(session: AsyncSession):
    """Create default market configurations if they don't exist."""
    try:
        # Check if markets already exist
        logger.info("Checking if default markets exist...")
        result = await session.execute(
            text("SELECT id FROM markets WHERE name IN ('Amazon', 'Walmart')")
        )
        markets = result.fetchall()
        
        if markets:
            logger.info("Default markets already exist, skipping creation")
            return
        
        # Create default markets for Amazon and Walmart
        amazon_id = str(uuid4())
        walmart_id = str(uuid4())
        system_user_id = "00000000-0000-4000-a000-000000000001"
        
        # Amazon market configuration
        amazon_config = {
            "country": "US",
            "max_results": 20,
            "search_index": "All"
        }
        
        # Insert Amazon market
        logger.info("Creating Amazon market...")
        await session.execute(
            text("""
            INSERT INTO markets (
                id, name, type, category, description, api_endpoint, api_key, user_id, 
                status, config, rate_limit, is_active, created_at, updated_at
            ) VALUES (
                :id, :name, :type, :category, :description, :api_endpoint, :api_key, :user_id, 
                :status, :config, :rate_limit, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """),
            {
                "id": amazon_id,
                "name": "Amazon",
                "type": "amazon",
                "category": "electronics",
                "description": "Amazon marketplace",
                "api_endpoint": "https://api.scraperapi.com/amazon",
                "api_key": "sample_key",
                "user_id": system_user_id,
                "status": "active",
                "config": json.dumps(amazon_config),
                "rate_limit": 50,
                "is_active": True
            }
        )
        
        # Walmart market configuration
        walmart_config = {
            "country": "US",
            "max_results": 20
        }
        
        # Insert Walmart market
        logger.info("Creating Walmart market...")
        await session.execute(
            text("""
            INSERT INTO markets (
                id, name, type, category, description, api_endpoint, api_key, user_id, 
                status, config, rate_limit, is_active, created_at, updated_at
            ) VALUES (
                :id, :name, :type, :category, :description, :api_endpoint, :api_key, :user_id, 
                :status, :config, :rate_limit, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """),
            {
                "id": walmart_id,
                "name": "Walmart",
                "type": "walmart",
                "category": "home",
                "description": "Walmart marketplace",
                "api_endpoint": "https://api.scraperapi.com/walmart",
                "api_key": "sample_key", 
                "user_id": system_user_id,
                "status": "active",
                "config": json.dumps(walmart_config),
                "rate_limit": 50,
                "is_active": True
            }
        )
        
        await session.commit()
        logger.info(f"Default markets created successfully: Amazon ({amazon_id}), Walmart ({walmart_id})")
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create default markets: {str(e)}")
        raise

async def run_initial_data_creation():
    """Run all initial data creation functions."""
    try:
        # Create default user (creates its own session internally)
        user_created = await create_default_user()
        if not user_created:
            logger.error("Failed to create default users")
            return False
        
        # Import database module
        from core.database import AsyncDatabaseSession
        
        # Use context manager for proper session management
        async with AsyncDatabaseSession() as session:
            try:
                # Create default markets
                await create_default_markets(session)
                
                logger.info("Initial data creation completed successfully")
                return True
                
            except Exception as e:
                logger.error(f"Initial data creation failed: {str(e)}")
                await session.rollback()
                return False
    
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        return False

def main():
    """Main entry point."""
    try:
        success = asyncio.run(run_initial_data_creation())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error in initial data creation: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 