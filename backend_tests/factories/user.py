"""User factory for tests."""

import uuid
import json
import hashlib
import bcrypt
from typing import Optional, Dict, Any
from datetime import datetime

from core.models.user import User
from core.models.user_preferences import UserPreferences
from core.models.enums import UserStatus

class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password using bcrypt.
        
        This matches the hashing method used in the User model.
        """
        # Generate a salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def create(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "TestPassword123!",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None,
        username: Optional[str] = None,  # Added for backward compatibility but not used
        **kwargs  # Capture any other parameters
    ) -> User:
        """Create a test user."""
        # Ignore username parameter if provided (for backward compatibility)
        if username is not None:
            # Use username as name if name is not provided
            if name is None:
                name = username
        
        # Make sure username is not in kwargs to avoid errors
        if 'username' in kwargs:
            del kwargs['username']
        
        # Default preferences if none provided
        if preferences is None:
            preferences = {
                "theme": "light",
                "language": "en",
                "timezone": "UTC",
                "minimum_priority": "low"
            }
        
        # Hash the password before storing it
        hashed_password = UserFactory._hash_password(password)
            
        # Create the user - don't set preferences directly because it's a relationship
        user = User(
            id=uuid.uuid4(),
            email=email or f"test-{uuid.uuid4()}@example.com",
            name=name or "Test User",
            password=hashed_password,  # Use the hashed password here
            status=status,
            email_verified=email_verified,
            **kwargs
        )
        
        # Add user to session first, so it has a valid id
        db_session.add(user)
        
        # Create UserPreferences instance and associate with user
        user_prefs = UserPreferences(
            user_id=user.id,
            user=user,
            theme=preferences.get("theme", "light"),
            language=preferences.get("language", "en"),
            timezone=preferences.get("timezone", "UTC"),
            minimum_priority=preferences.get("minimum_priority", "low"),
            email_digest=preferences.get("email_digest", True),
            push_enabled=preferences.get("push_enabled", True),
            sms_enabled=preferences.get("sms_enabled", False),
            telegram_enabled=preferences.get("telegram_enabled", False),
            discord_enabled=preferences.get("discord_enabled", False),
            do_not_disturb=preferences.get("do_not_disturb", False)
        )
        db_session.add(user_prefs)
        
        return user
    
    @staticmethod
    async def create_and_commit(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "TestPassword123!",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None,
        username: Optional[str] = None,  # Added for backward compatibility
        **kwargs  # Capture any other parameters
    ) -> User:
        """Create a test user and commit to the database."""
        user = UserFactory.create(
            db_session=db_session,
            email=email,
            name=name,
            password=password,
            status=status,
            email_verified=email_verified,
            preferences=preferences,
            username=username,
            **kwargs
        )
        
        await db_session.commit()
        await db_session.refresh(user)
        return user
        
    @staticmethod
    async def create_async(
        db_session,
        email: Optional[str] = None,
        name: Optional[str] = None,
        password: str = "TestPassword123!",
        status: str = UserStatus.ACTIVE.value.lower(),
        email_verified: bool = True,
        preferences: Optional[dict] = None,
        username: Optional[str] = None,  # Added for backward compatibility
        **kwargs  # Capture any other parameters
    ) -> User:
        """Create a test user asynchronously."""
        return await UserFactory.create_and_commit(
            db_session=db_session,
            email=email,
            name=name,
            password=password,
            status=status,
            email_verified=email_verified,
            preferences=preferences,
            username=username,
            **kwargs
        )
