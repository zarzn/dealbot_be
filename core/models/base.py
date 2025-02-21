"""Base model module.

This module defines the base model class and database configuration for the AI Agentic Deals System.
It provides common functionality and utilities used by all models.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar, ClassVar, TYPE_CHECKING
from uuid import UUID
import json
import logging

from sqlalchemy import Column, DateTime, text, MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import expression

from core.exceptions import DatabaseError

if TYPE_CHECKING:
    from sqlalchemy import Table

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Base')

# Configure metadata to allow table redefinition
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

class Base(DeclarativeBase):
    """Base model class with common functionality."""
    
    # Use the configured metadata
    metadata = metadata
    
    id: Any
    __table__: ClassVar['Table']
    
    # Common timestamp fields
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )
    
    @declared_attr
    def __tablename__(self) -> str:
        """Generate table name from class name."""
        return self.__class__.__name__.lower()
        
    @declared_attr
    def __table_args__(cls) -> Dict:
        """Configure table arguments."""
        return {'extend_existing': True}

    def dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self) -> str:
        """Convert model instance to JSON string."""
        def json_serializer(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, UUID):
                return str(obj)
            return str(obj)

        return json.dumps(self.dict(), default=json_serializer)

    @classmethod
    async def get_by_id(cls: Type[T], db: AsyncSession, id: UUID) -> Optional[T]:
        """Get model instance by ID."""
        try:
            instance = await db.get(cls, id)
            if not instance:
                logger.warning(f"{cls.__name__} with id {id} not found")
            return instance
        except Exception as e:
            logger.error(
                f"Error getting {cls.__name__} by id",
                extra={'id': str(id), 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Failed to get {cls.__name__}: {str(e)}",
                operation="get_by_id"
            )

    @classmethod
    async def create(cls: Type[T], db: AsyncSession, **kwargs) -> T:
        """Create a new model instance."""
        try:
            instance = cls(**kwargs)
            db.add(instance)
            await db.commit()
            await db.refresh(instance)
            logger.info(f"Created new {cls.__name__}", extra={'id': str(instance.id)})
            return instance
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error creating {cls.__name__}",
                extra={'kwargs': kwargs, 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Failed to create {cls.__name__}: {str(e)}",
                operation="create"
            )

    async def update(self: T, db: AsyncSession, **kwargs) -> T:
        """Update model instance."""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            await db.commit()
            await db.refresh(self)
            logger.info(
                f"Updated {self.__class__.__name__}",
                extra={'id': str(self.id), 'updates': kwargs}
            )
            return self
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error updating {self.__class__.__name__}",
                extra={'id': str(self.id), 'updates': kwargs, 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Failed to update {self.__class__.__name__}: {str(e)}",
                operation="update"
            )

    async def delete(self: T, db: AsyncSession) -> None:
        """Delete model instance."""
        try:
            await db.delete(self)
            await db.commit()
            logger.info(
                f"Deleted {self.__class__.__name__}",
                extra={'id': str(self.id)}
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error deleting {self.__class__.__name__}",
                extra={'id': str(self.id), 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Failed to delete {self.__class__.__name__}: {str(e)}",
                operation="delete"
            )
