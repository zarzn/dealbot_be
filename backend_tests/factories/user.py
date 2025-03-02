"""User factory for tests."""

import uuid
import json
from typing import Optional
from datetime import datetime

from core.models.user import User
from core.models.enums import UserStatus

class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "hashed_password_for_tests",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None
    ) -> User:
        """Create a test user."""
        # Ensure preferences is properly formatted for SQLAlchemy
        if preferences is None:
            preferences = {"test": True}
            
        # Create the user with proper fields
        user = User(
            id=uuid.uuid4(),
            email=email or f"test-{uuid.uuid4()}@example.com",
            name=name or "Test User",
            password=password,
            status=status,
            email_verified=email_verified,
            preferences=preferences
        )
        
        db_session.add(user)
        return user
    
    @staticmethod
    async def create_and_commit(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "hashed_password_for_tests",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None
    ) -> User:
        """Create a test user and commit to the database."""
        user = UserFactory.create(
            db_session=db_session,
            email=email,
            name=name,
            password=password,
            status=status,
            email_verified=email_verified,
            preferences=preferences
        )
        
        await db_session.commit()
        await db_session.refresh(user)
        return user
        
    @staticmethod
    async def create_async(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "hashed_password_for_tests",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None
    ) -> User:
        """Create a test user asynchronously."""
        return await UserFactory.create_and_commit(
            db_session=db_session,
            email=email,
            name=name,
            password=password,
            status=status,
            email_verified=email_verified,
            preferences=preferences
        )
