"""Database configuration module.

This module defines the database configuration, session management, and base repository pattern
for the AI Agentic Deals System.
"""

from datetime import datetime
from typing import Optional, TypeVar, Generic, List, Dict, Any
from uuid import UUID
import logging

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, JSON, DateTime, Enum, Integer, text, select, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy.sql import Select

from core.config import settings
from core.exceptions import DatabaseError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Base SQLAlchemy model
Base = declarative_base()

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

# Database configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Pydantic models for data validation
class GoalBase(BaseModel):
    user_id: UUID
    item_category: str = Field(..., max_length=255)
    title: str = Field(..., max_length=255)
    constraints: dict
    deadline: Optional[datetime] = None
    status: str = "active"
    priority: int = 1

class GoalCreate(GoalBase):
    pass

class GoalUpdate(BaseModel):
    item_category: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    constraints: Optional[dict] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None
    priority: Optional[int] = None

class GoalInDB(GoalBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_checked_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# SQLAlchemy model
class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    item_category: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    constraints: Mapped[dict] = mapped_column(JSON, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        Enum('active', 'paused', 'completed', 'expired', name='goal_status'), 
        default='active'
    )
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=text("NOW()"),
        onupdate=text("NOW()")
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )

# Base repository pattern
class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: type[ModelType]):
        """Initialize repository with model class."""
        self.model = model

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        try:
            db_obj = self.model(**obj_in.model_dump(exclude_unset=True))
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            
            logger.info(
                f"Created new {self.model.__name__}",
                extra={'id': str(getattr(db_obj, 'id', None))}
            )
            return db_obj
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error creating {self.model.__name__}",
                extra={'data': obj_in.model_dump(), 'error': str(e)}
            )
            raise DatabaseError(f"Error creating record: {str(e)}")

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get a record by ID."""
        try:
            db_obj = await db.get(self.model, id)
            if not db_obj:
                logger.warning(
                    f"{self.model.__name__} not found",
                    extra={'id': str(id)}
                )
                raise NotFoundError(f"{self.model.__name__} not found")
            return db_obj
            
        except Exception as e:
            logger.error(
                f"Error retrieving {self.model.__name__}",
                extra={'id': str(id), 'error': str(e)}
            )
            if isinstance(e, NotFoundError):
                raise
            raise DatabaseError(f"Error retrieving record: {str(e)}")

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple records with pagination and filtering."""
        try:
            query: Select = select(self.model)
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.filter(getattr(self.model, field) == value)
                        
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(
                f"Error retrieving multiple {self.model.__name__}",
                extra={
                    'skip': skip,
                    'limit': limit,
                    'filters': filters,
                    'error': str(e)
                }
            )
            raise DatabaseError(f"Error retrieving records: {str(e)}")

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType
    ) -> ModelType:
        """Update a record."""
        try:
            update_data = obj_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
                    
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            
            logger.info(
                f"Updated {self.model.__name__}",
                extra={
                    'id': str(getattr(db_obj, 'id', None)),
                    'updates': update_data
                }
            )
            return db_obj
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error updating {self.model.__name__}",
                extra={
                    'id': str(getattr(db_obj, 'id', None)),
                    'updates': obj_in.model_dump(),
                    'error': str(e)
                }
            )
            raise DatabaseError(f"Error updating record: {str(e)}")

    async def delete(self, db: AsyncSession, *, id: UUID) -> None:
        """Delete a record."""
        try:
            db_obj = await self.get(db, id)
            await db.delete(db_obj)
            await db.commit()
            
            logger.info(
                f"Deleted {self.model.__name__}",
                extra={'id': str(id)}
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Error deleting {self.model.__name__}",
                extra={'id': str(id), 'error': str(e)}
            )
            if isinstance(e, NotFoundError):
                raise
            raise DatabaseError(f"Error deleting record: {str(e)}")

    async def count(
        self,
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count total records with optional filtering."""
        try:
            query = select(func.count()).select_from(self.model)
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.filter(getattr(self.model, field) == value)
                        
            result = await db.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(
                f"Error counting {self.model.__name__}",
                extra={'filters': filters, 'error': str(e)}
            )
            raise DatabaseError(f"Error counting records: {str(e)}")

# Goal-specific repository
class GoalRepository(BaseRepository[Goal, GoalCreate, GoalUpdate]):
    def __init__(self):
        super().__init__(Goal)

# Database session dependency
async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", extra={'error': str(e)})
            raise DatabaseError(f"Database session error: {str(e)}")
        finally:
            await session.close()
