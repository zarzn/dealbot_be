from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from backend.core.models.user import User
from backend.core.exceptions import (
    DatabaseError,
    UserNotFoundError,
    DuplicateUserError,
    RepositoryError
)
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_user(self, user_data: dict) -> User:
        """Create a new user with proper error handling"""
        try:
            existing_user = self.db.query(User).filter(
                User.email == user_data['email']
            ).first()
            if existing_user:
                raise DuplicateUserError(f"User with email {user_data['email']} already exists")

            new_user = User(**user_data)
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            return new_user

        except DuplicateUserError as e:
            logger.error(f"Duplicate user error: {str(e)}")
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating user: {str(e)}")
            raise DatabaseError("Failed to create user") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating user: {str(e)}")
            raise RepositoryError("Unexpected error occurred") from e

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by ID with error handling"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundError(f"User with ID {user_id} not found")
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user: {str(e)}")
            raise DatabaseError("Failed to retrieve user") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving user: {str(e)}")
            raise RepositoryError("Unexpected error occurred") from e

    async def update_user(self, user_id: str, update_data: dict) -> User:
        """Update user information with error handling"""
        try:
            user = await self.get_user_by_id(user_id)
            for key, value in update_data.items():
                setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating user: {str(e)}")
            raise DatabaseError("Failed to update user") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating user: {str(e)}")
            raise RepositoryError("Unexpected error occurred") from e

    async def delete_user(self, user_id: str) -> bool:
        """Delete user with proper error handling"""
        try:
            user = await self.get_user_by_id(user_id)
            self.db.delete(user)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting user: {str(e)}")
            raise DatabaseError("Failed to delete user") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error deleting user: {str(e)}")
            raise RepositoryError("Unexpected error occurred") from e

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieve user by email with error handling"""
        try:
            user = self.db.query(User).filter(User.email == email).first()
            if not user:
                raise UserNotFoundError(f"User with email {email} not found")
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving user by email: {str(e)}")
            raise DatabaseError("Failed to retrieve user by email") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving user by email: {str(e)}")
            raise RepositoryError("Unexpected error occurred") from e
