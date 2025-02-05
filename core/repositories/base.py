"""Base repository module providing common database operations."""

import logging
from typing import Any, Generic, TypeVar, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from core.exceptions import (
    DatabaseError,
    ValidationError,
    BaseError
)

logger = logging.getLogger(__name__)
T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class providing common CRUD operations.
    
    This class serves as a base for all repository implementations, providing
    common database operations and error handling.
    
    Attributes:
        db (AsyncSession): The database session for executing operations
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """Initialize the repository with a database session.
        
        Args:
            db: The database session to use for operations
        """
        self.db = db

    async def commit(self) -> None:
        """Commit the current transaction.
        
        Raises:
            DatabaseError: If the commit operation fails
        """
        try:
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Failed to commit transaction: {str(e)}")
            raise DatabaseError("Database operation failed") from e

    async def refresh(self, entity: T) -> None:
        """Refresh the state of an entity.
        
        Args:
            entity: The entity to refresh
            
        Raises:
            DatabaseError: If the refresh operation fails
        """
        try:
            await self.db.refresh(entity)
        except SQLAlchemyError as e:
            logger.error(f"Failed to refresh entity: {str(e)}")
            raise DatabaseError("Failed to refresh entity") from e

    async def execute(self, statement: Any) -> Any:
        """Execute a SQLAlchemy statement.
        
        Args:
            statement: The SQLAlchemy statement to execute
            
        Returns:
            The result of the statement execution
            
        Raises:
            DatabaseError: If the statement execution fails
        """
        try:
            return await self.db.execute(statement)
        except SQLAlchemyError as e:
            logger.error(f"Failed to execute statement: {str(e)}")
            raise DatabaseError("Failed to execute statement") from e
