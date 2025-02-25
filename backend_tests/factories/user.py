from typing import Optional
from factory import Faker
from .base import BaseFactory
from core.models.user import User
from core.models.enums import UserStatus
from core.services.auth import get_password_hash
from uuid import uuid4
import bcrypt

class UserFactory(BaseFactory):
    class Meta:
        model = User

    _sequence = 1

    @classmethod
    def _get_next_sequence(cls):
        value = cls._sequence
        cls._sequence += 1
        return value

    @classmethod
    async def create_async(cls, db_session=None, **kwargs):
        """Create a new user instance with a valid email and password.
        
        Args:
            db_session: Database session (required)
            **kwargs: Additional user attributes
            
        Returns:
            User: The created user instance
            
        Raises:
            ValueError: If db_session is not provided
        """
        if db_session is None:
            raise ValueError("db_session is required for create_async")
        
        if 'email' not in kwargs:
            # Use UUID to ensure uniqueness
            unique_id = str(uuid4())[:8]
            kwargs['email'] = f'test_{unique_id}@example.com'
        
        if 'password' not in kwargs:
            # Set a default password for testing
            kwargs['password'] = 'testpassword123'
        
        # Use the same password hashing function as the auth service
        plain_password = kwargs['password']
        kwargs['password'] = get_password_hash(plain_password)
        
        if 'status' not in kwargs:
            kwargs['status'] = UserStatus.ACTIVE.value

        return await super().create_async(db_session=db_session, **kwargs)
