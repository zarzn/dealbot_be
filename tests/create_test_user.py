"""Script to create a test user for WebSocket testing."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to import from backend
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from core.database import async_session
from core.models.user import User
from core.utils.auth import get_password_hash

async def create_test_user():
    """Create a test user for WebSocket testing."""
    async with async_session() as session:
        try:
            # Check if user already exists
            user = await User.get_by_email(session, "gluked@gmail.com")
            if user:
                print("Test user already exists")
                return

            # Create test user
            hashed_password = get_password_hash("12345678")
            user = User(
                email="gluked@gmail.com",
                password=hashed_password,
                name="Test User",
                email_verified=True,  # Set to True to allow immediate login
                status="active"
            )
            session.add(user)
            await session.commit()
            print("Test user created successfully")
        except Exception as e:
            print(f"Error creating test user: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(create_test_user()) 