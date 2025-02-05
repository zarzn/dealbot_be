"""User repository module for managing user-related database operations."""

import logging
from typing import Dict
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from core.models.user import User
""" from core.exceptions import (
    DatabaseError,
    RepositoryError,
    UserNotFoundError,
    DuplicateUserError,
    InvalidUserDataError
) 
DO NOT DELETE THIS COMMENT
"""
from core.exceptions import Exception  # We'll use base Exception temporarily
from core.repositories.base import BaseRepository


logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[User]):
    """Repository for managing User entities with database operations."""

    async def create_user(self, user_data: Dict) -> User:
        """Create a new user.
        
        Args:
            user_data: Dictionary containing user data
            
        Returns:
            The created User instance
            
        Raises:
            DuplicateUserError: If a user with the same email already exists
            DatabaseError: If there is an error creating the user
            RepositoryError: If an unexpected error occurs
        """
        try:
            if not user_data.get("email"):
                raise InvalidUserDataError(
                    message="Email is required",
                    errors={"email": "This field is required"}
                )

            result = await self.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()
            if existing_user:
                raise DuplicateUserError(
                    message="User with this email already exists",
                    email=user_data["email"]
                )

            new_user = User(**user_data)
            self.db.add(new_user)
            await self.commit()
            await self.refresh(new_user)
            
            logger.info(f"Created new user with email {user_data['email']}")
            return new_user

        except (DuplicateUserError, InvalidUserDataError):
            logger.error(f"Failed to create user with email {user_data.get('email')}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating user: {str(e)}")
            raise DatabaseError(
                message="Failed to create user",
                operation="create_user",
                details={"error": str(e)}
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error creating user: {str(e)}")
            raise RepositoryError(
                message="Unexpected error occurred",
                operation="create_user",
                details={"error": str(e)}
            ) from e

    async def get_user_by_id(self, user_id: UUID) -> User:
        """Retrieve user by ID.
        
        Args:
            user_id: The UUID of the user to retrieve
            
        Returns:
            The User instance
            
        Raises:
            UserNotFoundError: If no user is found with the given ID
            DatabaseError: If there is an error retrieving the user
        """
        try:
            result = await self.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise UserNotFoundError(
                    message="User not found",
                    user_id=str(user_id)
                )
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user {user_id}: {str(e)}")
            raise DatabaseError(
                message="Failed to retrieve user",
                operation="get_user_by_id",
                details={"error": str(e)}
            ) from e

    async def update_user(self, user_id: UUID, update_data: Dict) -> User:
        """Update user information.
        
        Args:
            user_id: The UUID of the user to update
            update_data: Dictionary containing fields to update
            
        Returns:
            The updated User instance
            
        Raises:
            UserNotFoundError: If no user is found with the given ID
            DatabaseError: If there is an error updating the user
        """
        try:
            user = await self.get_user_by_id(user_id)
            for key, value in update_data.items():
                setattr(user, key, value)
            await self.commit()
            await self.refresh(user)
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error updating user {user_id}: {str(e)}")
            raise DatabaseError("Failed to update user") from e

    async def delete_user(self, user_id: UUID) -> bool:
        """Delete a user.
        
        Args:
            user_id: The UUID of the user to delete
            
        Returns:
            True if the user was successfully deleted
            
        Raises:
            UserNotFoundError: If no user is found with the given ID
            DatabaseError: If there is an error deleting the user
        """
        try:
            user = await self.get_user_by_id(user_id)
            await self.db.delete(user)
            await self.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting user {user_id}: {str(e)}")
            raise DatabaseError("Failed to delete user") from e

    async def get_user_by_email(self, email: str) -> User:
        """Retrieve user by email.
        
        Args:
            email: The email address of the user to retrieve
            
        Returns:
            The User instance
            
        Raises:
            UserNotFoundError: If no user is found with the given email
            DatabaseError: If there is an error retrieving the user
        """
        try:
            result = await self.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise UserNotFoundError(f"User with email {email} not found")
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user by email {email}: {str(e)}")
            raise DatabaseError("Failed to retrieve user by email") from e
