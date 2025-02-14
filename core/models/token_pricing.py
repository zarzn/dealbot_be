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
from enum import Enum as PyEnum
from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column, String, DateTime, Numeric, Boolean, text, DECIMAL, 
    Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func, expression
from core.models.base import Base
from core.exceptions import ValidationError, TokenError

class ServiceType(str, PyEnum):
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
            raise ValidationError("valid_to must be after valid_from")
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
    __table_args__ = (
        Index('ix_token_pricing_service', 'service_type'),
        Index('ix_token_pricing_active', 'is_active'),
        CheckConstraint('token_cost > 0', name='ch_positive_cost'),
        CheckConstraint('valid_to > valid_from', name='ch_valid_dates'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_type: Mapped[ServiceType] = mapped_column(SQLEnum(ServiceType), nullable=False)
    token_cost: Mapped[Decimal] = mapped_column(DECIMAL(18, 8), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))

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
