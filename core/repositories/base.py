"""Base repository module providing common database operations."""

import logging
from typing import Any, Generic, TypeVar, Optional, List, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, update, delete
from sqlalchemy.sql import Select

from core.exceptions import (
    DatabaseError,
    ValidationError,
    BaseError,
    NotFoundError
)

logger = logging.getLogger(__name__)
T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class providing common CRUD operations.
    
    This class serves as a base for all repository implementations, providing
    common database operations and error handling.
    
    Attributes:
        db (AsyncSession): The database session for executing operations
        model (Type[T]): The SQLAlchemy model class
    """
    
    def __init__(self, db: AsyncSession, model: Type[T]) -> None:
        """Initialize the repository with a database session and model.
        
        Args:
            db: The database session to use for operations
            model: The SQLAlchemy model class
        """
        self.db = db
        self.model = model

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

    async def create(self, **kwargs: Any) -> T:
        """Create a new entity.
        
        Args:
            **kwargs: The attributes to set on the new entity
            
        Returns:
            The created entity
            
        Raises:
            ValidationError: If the entity data is invalid
            DatabaseError: If the creation fails
        """
        try:
            entity = self.model(**kwargs)
            self.db.add(entity)
            await self.commit()
            await self.refresh(entity)
            return entity
        except ValidationError as e:
            logger.error(f"Validation error creating entity: {str(e)}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating entity: {str(e)}")
            raise DatabaseError("Failed to create entity") from e

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get an entity by ID.
        
        Args:
            id: The ID of the entity to get
            
        Returns:
            The entity if found, None otherwise
            
        Raises:
            DatabaseError: If the query fails
        """
        try:
            query = select(self.model).where(self.model.id == id)
            result = await self.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting entity by ID: {str(e)}")
            raise DatabaseError("Failed to get entity") from e

    async def get_all(self) -> List[T]:
        """Get all entities.
        
        Returns:
            List of all entities
            
        Raises:
            DatabaseError: If the query fails
        """
        try:
            query = select(self.model)
            result = await self.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Database error getting all entities: {str(e)}")
            raise DatabaseError("Failed to get entities") from e

    async def update(self, id: UUID, **kwargs: Any) -> Optional[T]:
        """Update an entity by ID.
        
        Args:
            id: The ID of the entity to update
            **kwargs: The attributes to update
            
        Returns:
            The updated entity if found, None otherwise
            
        Raises:
            ValidationError: If the update data is invalid
            DatabaseError: If the update fails
        """
        try:
            query = (
                update(self.model)
                .where(self.model.id == id)
                .values(**kwargs)
                .returning(self.model)
            )
            result = await self.execute(query)
            entity = result.scalar_one_or_none()
            if entity:
                await self.commit()
            return entity
        except ValidationError as e:
            logger.error(f"Validation error updating entity: {str(e)}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating entity: {str(e)}")
            raise DatabaseError("Failed to update entity") from e

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID.
        
        Args:
            id: The ID of the entity to delete
            
        Returns:
            True if the entity was deleted, False if not found
            
        Raises:
            DatabaseError: If the deletion fails
        """
        try:
            query = delete(self.model).where(self.model.id == id)
            result = await self.execute(query)
            deleted = result.rowcount > 0
            if deleted:
                await self.commit()
            return deleted
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting entity: {str(e)}")
            raise DatabaseError("Failed to delete entity") from e

    def filter(self, *criterion: Any) -> Select:
        """Create a SELECT query with filters.
        
        Args:
            *criterion: SQLAlchemy filter criteria
            
        Returns:
            The SELECT query
        """
        return select(self.model).where(*criterion)
