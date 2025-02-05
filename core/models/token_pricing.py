"""Token Pricing model module.

This module defines the TokenPricing model and related Pydantic schemas for managing
token pricing in the AI Agentic Deals System.

Classes:
    ServiceType: Enum for service types
    TokenPricingBase: Base Pydantic model for pricing data
    TokenPricingCreate: Model for pricing creation
    TokenPricingUpdate: Model for pricing updates
    TokenPricingInDB: Model for database representation
    TokenPricing: SQLAlchemy model for database table
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, String, DateTime, Numeric, Boolean, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base
from core.exceptions import (
    ValidationError,
    TokenError,
    TokenPricingError,
    InvalidPricingError
)

class ServiceType(str, Enum):
    SEARCH = "search"
    NOTIFICATION = "notification"
    ANALYSIS = "analysis"
    CHAT = "chat"

class TokenPricingBase(BaseModel):
    service_type: ServiceType
    token_cost: float = Field(..., gt=0)
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = Field(default=True)

    @field_validator('valid_to')
    @classmethod
    def validate_dates(cls, v: Optional[datetime], values: dict) -> Optional[datetime]:
        if v and 'valid_from' in values and v <= values['valid_from']:
            raise InvalidPricingError("valid_to must be after valid_from")
        return v

class TokenPricingCreate(TokenPricingBase):
    pass

class TokenPricingUpdate(BaseModel):
    token_cost: Optional[float] = Field(None, gt=0)
    valid_to: Optional[datetime] = None
    is_active: Optional[bool] = None

class TokenPricingInDB(TokenPricingBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class TokenPricing(Base):
    __tablename__ = 'token_pricing'

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    token_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('NOW()'))

    def __repr__(self):
        return f"<TokenPricing {self.id}>"

    @classmethod
    async def create(cls, db, **kwargs) -> 'TokenPricing':
        """Create a new token pricing record with proper validation"""
        try:
            pricing = cls(**kwargs)
            db.add(pricing)
            await db.commit()
            await db.refresh(pricing)
            return pricing
        except Exception as e:
            await db.rollback()
            raise ValueError(f"Failed to create pricing: {str(e)}") from e

    @classmethod
    async def get_active_pricing(cls, db) -> list['TokenPricing']:
        """Get all active pricing records"""
        now = datetime.utcnow()
        return await db.query(cls)\
            .filter(cls.is_active == True)\
            .filter(cls.valid_from <= now)\
            .filter((cls.valid_to == None) | (cls.valid_to >= now))\
            .all()

    @classmethod
    async def get_by_service_type(cls, db, service_type: ServiceType) -> Optional['TokenPricing']:
        """Get active pricing for a specific service type"""
        now = datetime.utcnow()
        return await db.query(cls)\
            .filter(cls.service_type == service_type)\
            .filter(cls.is_active == True)\
            .filter(cls.valid_from <= now)\
            .filter((cls.valid_to == None) | (cls.valid_to >= now))\
            .first()
