"""Database configuration module.

This module defines the database configuration, session management, and base repository pattern
for the AI Agentic Deals System.
"""

from datetime import datetime
from typing import Optional, TypeVar, Generic, List, Dict, Any, AsyncGenerator
from uuid import UUID
import logging

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, JSON, DateTime, Enum, Integer, text, select, func, Float, ForeignKey, Boolean, Numeric
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column, relationship
from sqlalchemy.sql import Select

from core.config import settings
from core.database import async_engine, AsyncSessionLocal, Base
from core.exceptions.base_exceptions import (
    DatabaseError,
    ValidationError,
    NotFoundError,
    RepositoryError
)

logger = logging.getLogger(__name__)

# Base SQLAlchemy model
Base = declarative_base()

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

# Move User import inside functions where needed
def get_user_model():
    from core.models.user import User
    return User

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
                "Error creating record",
                extra={'data': obj_in.model_dump(), 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Error creating record: {str(e)}",
                operation="create"
            )

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get a record by ID."""
        try:
            db_obj = await db.get(self.model, id)
            if not db_obj:
                logger.warning(
                    f"{self.model.__name__} not found",
                    extra={'id': str(id)}
                )
                raise NotFoundError(
                    message=f"{self.model.__name__} not found",
                    resource_type=self.model.__name__.lower(),
                    resource_id=str(id)
                )
            return db_obj
            
        except Exception as e:
            logger.error(
                f"Error retrieving {self.model.__name__}",
                extra={'id': str(id), 'error': str(e)}
            )
            if isinstance(e, NotFoundError):
                raise
            raise DatabaseError(
                message=f"Error retrieving record: {str(e)}",
                operation="get"
            )

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
            raise DatabaseError(
                message=f"Error retrieving records: {str(e)}",
                operation="get_multi"
            )

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
            raise DatabaseError(
                message=f"Error updating record: {str(e)}",
                operation="update"
            )

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
            raise DatabaseError(
                message=f"Error deleting record: {str(e)}",
                operation="delete"
            )

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
                    query = query.where(getattr(self.model, field) == value)
                        
            result = await db.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(
                f"Error counting {self.model.__name__}",
                extra={'filters': filters, 'error': str(e)}
            )
            raise DatabaseError(
                message=f"Error counting records: {str(e)}",
                operation="count"
            )

# Goal-specific repository
class GoalRepository(BaseRepository[Goal, GoalCreate, GoalUpdate]):
    def __init__(self):
        super().__init__(Goal)

# Database session dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", extra={'error': str(e)})
            raise DatabaseError(
                message=f"Database session error: {str(e)}",
                operation="session_management"
            )
        finally:
            await session.close()

"""Database models for price tracking and prediction."""

class PricePoint(Base):
    """Price point record in database."""
    __tablename__ = "price_points"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="USD")
    source = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    meta_data = Column(JSON)

    # Relationships
    deal = relationship("Deal", back_populates="price_points")

class PriceTracker(Base):
    """Price tracker configuration in database."""
    __tablename__ = "price_trackers"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    initial_price = Column(Numeric(10, 2), nullable=False)
    threshold_price = Column(Numeric(10, 2))
    check_interval = Column(Integer, default=300)  # seconds
    last_check = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    notification_settings = Column(JSON)
    meta_data = Column(JSON)

    # Relationships
    deal = relationship("Deal", back_populates="price_tracker")
    user = relationship("User", back_populates="price_trackers", lazy="selectin")

class PricePrediction(Base):
    """Price prediction record in database."""
    __tablename__ = "price_predictions"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String, nullable=False)
    prediction_days = Column(Integer, default=7)
    confidence_threshold = Column(Float, default=0.8)
    predictions = Column(JSON, nullable=False)  # List of prediction points
    overall_confidence = Column(Float, nullable=False)
    trend_direction = Column(String)
    trend_strength = Column(Float)
    seasonality_score = Column(Float)
    features_used = Column(JSON)  # List of features
    model_params = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    meta_data = Column(JSON)

    # Relationships
    deal = relationship("Deal", back_populates="price_predictions")
    user = relationship("User", back_populates="price_predictions", lazy="selectin")

class ModelMetrics(Base):
    """Model performance metrics in database."""
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    accuracy = Column(Float, nullable=False)
    mae = Column(Float, nullable=False)
    mse = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    mape = Column(Float, nullable=False)
    r2_score = Column(Float, nullable=False)
    training_time = Column(Float)
    prediction_time = Column(Float)
    last_retrain = Column(DateTime, nullable=False)
    feature_importance = Column(JSON)
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Update Deal model relationships
from core.models.deal import Deal
Deal.price_points = relationship("PricePoint", back_populates="deal", cascade="all, delete-orphan")
Deal.price_tracker = relationship("PriceTracker", back_populates="deal", uselist=False, cascade="all, delete-orphan")
Deal.price_predictions = relationship("PricePrediction", back_populates="deal", cascade="all, delete-orphan")

# Update User model relationships
from core.models.user import User
User.price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")
User.price_predictions = relationship("PricePrediction", back_populates="user", cascade="all, delete-orphan")
