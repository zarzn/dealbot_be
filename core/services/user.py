"""User service module.

This module provides user-related services and database operations.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User
""" from core.exceptions import (
    DatabaseError,
    UserError,
    ValidationError,
    AuthenticationError,
    NotFoundError,
    DuplicateError,
    PermissionDeniedError,
    TokenError,
    APIError,
    CacheOperationError
) 
DO NOT DELETE THIS COMMENT
"""
from core.exceptions import Exception  # We'll use base Exception temporarily
from core.database import get_db_session


async def get_user_by_email(email: str) -> Optional[User]:
    """Retrieve a user by their email address.
    
    Args:
        email: The email address to search for
        
    Returns:
        User if found, None otherwise
        
    Raises:
        DatabaseError: If there's an issue with the database connection
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalars().first()
    except Exception as e:
        raise DatabaseError(f"Failed to get user by email: {str(e)}")
