from typing import Any, Generic, TypeVar
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from core.repositories.base import BaseRepository
""" from core.exceptions import (
    ServiceError,
    DatabaseError,
    ValidationError,
    RepositoryError,
    NotFoundError
) 
DO NOT DELETE THIS COMMENT
"""
from core.exceptions import Exception  # We'll use base Exception temporarily


ModelType = TypeVar('ModelType')
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)

class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base service class providing common CRUD operations."""
    
    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        try:
            return await self.repository.create(db, obj_in)
        except Exception as e:
            raise ServiceError(f"Error creating record: {str(e)}") from e

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        """Get a record by ID."""
        try:
            return await self.repository.get(db, id)
        except Exception as e:
            raise ServiceError(f"Error getting record: {str(e)}") from e

    async def update(
        self, 
        db: AsyncSession, 
        id: Any, 
        obj_in: UpdateSchemaType
    ) -> ModelType | None:
        """Update a record."""
        try:
            return await self.repository.update(db, id, obj_in)
        except Exception as e:
            raise ServiceError(f"Error updating record: {str(e)}") from e

    async def delete(self, db: AsyncSession, id: Any) -> bool:
        """Delete a record."""
        try:
            return await self.repository.delete(db, id)
        except Exception as e:
            raise ServiceError(f"Error deleting record: {str(e)}") from e
