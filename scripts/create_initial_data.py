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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

async def create_default_user():
    """Create a default user if it doesn't exist."""
    try:
        # Import database module
        from core.database import get_async_db_session
        
        # Get database session
        logger.info("Connecting to database...")
        session = await get_async_db_session()
        
        try:
            # Check if user already exists using raw SQL
            logger.info("Checking if default user exists...")
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": "test@test.com"}
            )
            user = result.fetchone()
            
            if user:
                logger.info("Default user already exists, skipping creation")
                return True
            
            # Create default user
            logger.info("Creating default user...")
            hashed_password = get_password_hash("Qwerty123!")
            user_id = str(uuid4())
            
            # Insert user directly with SQL to avoid mapper issues
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
                    "id": user_id,
                    "email": "test@test.com",
                    "name": "Test User",
                    "password": hashed_password,
                    "status": "active",
                    "preferences": "{}",
                    "notification_channels": "[]",
                    "email_verified": True
                }
            )
            
            await session.commit()
            
            logger.info(f"Default user created successfully with ID: {user_id}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to create default user: {str(e)}")
            return False
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return False

async def run_initial_data_creation():
    """Run all initial data creation functions."""
    try:
        logger.info("Starting initial data creation...")
        
        # Create default user
        if not await create_default_user():
            logger.error("Failed to create default user")
            return False
        
        # Add more initial data creation functions here as needed
        
        logger.info("Initial data creation completed successfully")
        return True
    except Exception as e:
        logger.error(f"Initial data creation failed: {str(e)}")
        return False

def main():
    """Main entry point."""
    success = asyncio.run(run_initial_data_creation())
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 