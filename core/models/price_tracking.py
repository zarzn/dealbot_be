"""Price tracking models."""

from datetime import datetime
from typing import Optional, Dict
from uuid import UUID
from decimal import Decimal

from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, Field

from core.models.base import Base
from core.models.deal import Deal
from core.models.user import User

class PricePoint(Base):
    """SQLAlchemy model for price points."""
    __tablename__ = "price_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    currency: Mapped[str] = mapped_column(String, server_default="USD")
    source: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    meta_data: Mapped[Optional[Dict]] = mapped_column(JSONB)

    # Relationships
    deal = relationship("Deal", back_populates="price_points")

class PriceTracker(Base):
    """SQLAlchemy model for price trackers."""
    __tablename__ = "price_trackers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    initial_price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    threshold_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=10, scale=2))
    check_interval: Mapped[int] = mapped_column(Integer, server_default="300")
    last_check: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", index=True)
    notification_settings: Mapped[Optional[Dict]] = mapped_column(JSONB)
    meta_data: Mapped[Optional[Dict]] = mapped_column(JSONB)

    # Relationships
    deal = relationship("Deal", back_populates="price_trackers")
    user = relationship("User", back_populates="price_trackers")

# Pydantic models
class PricePointBase(BaseModel):
    """Base model for price points."""
    deal_id: UUID
    price: Decimal = Field(gt=0)
    currency: str = "USD"
    source: str
    metadata: Optional[Dict] = None

class PricePointCreate(PricePointBase):
    """Schema for creating a price point."""
    pass

class PricePointResponse(PricePointBase):
    """Schema for price point response."""
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class PriceTrackerBase(BaseModel):
    """Base model for price trackers."""
    deal_id: UUID
    threshold_price: Optional[Decimal] = Field(gt=0, default=None)
    check_interval: int = Field(ge=60, default=300)  # minimum 60 seconds
    notification_settings: Optional[Dict] = None
    metadata: Optional[Dict] = None

class PriceTrackerCreate(PriceTrackerBase):
    """Schema for creating a price tracker."""
    pass

class PriceTrackerResponse(PriceTrackerBase):
    """Schema for price tracker response."""
    id: int
    initial_price: Decimal
    last_check: datetime
    is_active: bool
    current_price: Optional[Decimal] = None
    price_change: Optional[Decimal] = None
    price_change_percentage: Optional[float] = None
    status: str

    class Config:
        from_attributes = True

class PriceTrackerUpdate(BaseModel):
    """Schema for updating a price tracker."""
    threshold_price: Optional[Decimal] = Field(gt=0, default=None)
    check_interval: Optional[int] = Field(ge=60, default=None)
    notification_settings: Optional[Dict] = None
    is_active: Optional[bool] = None

class PriceStatistics(BaseModel):
    """Schema for price statistics."""
    min_price: Decimal
    max_price: Decimal
    avg_price: Decimal
    median_price: Decimal
    price_volatility: float
    total_points: int
    time_range: str
    last_update: datetime
    trend: str
    metadata: Optional[Dict] = None 