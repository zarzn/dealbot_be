"""Base service module."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.models.base import Base
from core.repositories.base import BaseRepository
from core.exceptions import (
    ServiceError,
    DatabaseError,
    ValidationError,
    RepositoryError,
    NotFoundError,
    BaseError
)

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")

class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for all services."""
    
    model: Type[ModelType]
    
    def __init__(self, session: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize service.
        
        Args:
            session: Database session
            redis_service: Optional Redis service for caching
        """
        self.db = session
        self._redis = redis_service
        
        # Check if model is defined in the subclass
        if not hasattr(self, 'model'):
            raise TypeError("Service class must define 'model' attribute")
        
        self.repository = BaseRepository[ModelType](session, self.model)

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        try:
            return await self.repository.create(db, obj_in)
        except BaseError as e:
            raise ServiceError(f"Error creating record: {str(e)}") from e

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        """Get a record by ID."""
        try:
            return await self.repository.get(db, id)
        except BaseError as e:
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
        except BaseError as e:
            raise ServiceError(f"Error updating record: {str(e)}") from e

    async def delete(self, db: AsyncSession, id: Any) -> bool:
        """Delete a record."""
        try:
            return await self.repository.delete(db, id)
        except BaseError as e:
            raise ServiceError(f"Error deleting record: {str(e)}") from e
