"""Base model module.

This module defines the base model class and database configuration for the AI Agentic Deals System.
It provides common functionality and utilities used by all models.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar, ClassVar, TYPE_CHECKING
from uuid import UUID
import json
import logging

from sqlalchemy import Column, DateTime, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import expression

from core.config import settings
from core.exceptions import DatabaseError

if TYPE_CHECKING:
    from sqlalchemy import Table

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Base')

class Base(DeclarativeBase):
    """Base model class with common functionality."""
    
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
            raise DatabaseError(f"Failed to get {cls.__name__}: {str(e)}")

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
            raise DatabaseError(f"Failed to create {cls.__name__}: {str(e)}")

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
            raise DatabaseError(f"Failed to update {self.__class__.__name__}: {str(e)}")

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
            raise DatabaseError(f"Failed to delete {self.__class__.__name__}: {str(e)}")

# Database configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", extra={'error': str(e)})
            raise DatabaseError(f"Database session error: {str(e)}")
        finally:
            await session.close()
