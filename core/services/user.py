from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models.user import User
from backend.core.exceptions import DatabaseError
from backend.core.database import async_session

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
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalars().first()
    except Exception as e:
        raise DatabaseError(f"Failed to get user by email: {str(e)}")
