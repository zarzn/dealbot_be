"""Deal model module.

This module defines the deal-related models for the AI Agentic Deals System,
including deal status tracking, scoring, and price history.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, HttpUrl, Field, validator, conint, confloat
import enum

from sqlalchemy import (
    ForeignKey, String, Text, DECIMAL, JSON, Enum as SQLAlchemyEnum,
    UniqueConstraint, CheckConstraint, Index, Column, DateTime
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import expression

from core.models.base import Base

class DealStatus(str, enum.Enum):
    """Deal status types."""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"
    PENDING = "pending"
    SOLD_OUT = "sold_out"
    PRICE_CHANGED = "price_changed"

class DealSource(str, enum.Enum):
    """Deal source types."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    TARGET = "target"
    BESTBUY = "bestbuy"
    MANUAL = "manual"

class DealBase(BaseModel):
    """Base deal model."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    url: HttpUrl
    price: Decimal
    original_price: Optional[Decimal] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    source: str = Field(..., min_length=1, max_length=50)
    image_url: Optional[HttpUrl] = None
    deal_metadata: Optional[Dict[str, Any]] = None
    price_metadata: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    status: DealStatus = Field(default=DealStatus.ACTIVE)

    @validator('original_price')
    def validate_original_price(cls, v: Optional[Decimal], values: Dict[str, Any]) -> Optional[Decimal]:
        """Validate original price is greater than current price."""
        if v is not None and 'price' in values and v <= values['price']:
            raise ValueError("Original price must be greater than current price")
        return v

    @validator('expires_at')
    def validate_expiry(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate expiry date is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiry date must be in the future")
        return v

class DealCreate(DealBase):
    """Deal creation model."""
    goal_id: UUID
    market_id: UUID
    category: Optional[str] = None
    seller_info: Optional[Dict[str, Any]] = None
    availability: Optional[Dict[str, Any]] = None

class DealUpdate(BaseModel):
    """Deal update model."""
    price: Optional[Decimal] = Field(None, gt=0)
    original_price: Optional[Decimal] = Field(None, gt=0)
    status: Optional[DealStatus] = None
    expires_at: Optional[datetime] = None
    deal_metadata: Optional[Dict[str, Any]] = None
    availability: Optional[Dict[str, Any]] = None

    @validator('original_price')
    def validate_original_price(cls, v: Optional[Decimal], values: Dict[str, Any]) -> Optional[Decimal]:
        """Validate original price is greater than current price."""
        if v is not None and 'price' in values and values['price'] is not None and v <= values['price']:
            raise ValueError("Original price must be greater than current price")
        return v

class DealResponse(DealBase):
    """Deal response model."""
    id: UUID
    goal_id: UUID
    market_id: UUID
    found_at: datetime
    status: DealStatus
    category: Optional[str]
    seller_info: Optional[Dict[str, Any]]
    availability: Optional[Dict[str, Any]]
    latest_score: Optional[float]
    price_history: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: float
        }

class Deal(Base):
    """Deal database model."""
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint('url', 'goal_id', name='uq_deal_url_goal'),
        CheckConstraint('price > 0', name='ch_positive_price'),
        CheckConstraint(
            'original_price IS NULL OR original_price > price',
            name='ch_original_price_gt_price'
        ),
        Index('ix_deals_status_found', 'status', 'found_at'),
        Index('ix_deals_goal_status', 'goal_id', 'status'),
        Index('ix_deals_market_status', 'market_id', 'status'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=True)
    market_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2))
    original_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(String(50))
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    found_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[DealStatus] = mapped_column(SQLAlchemyEnum(DealStatus), default=DealStatus.ACTIVE)
    seller_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    availability: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    deal_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    price_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    goal = relationship("Goal", back_populates="deals")
    market = relationship("Market", back_populates="deals")
    scores = relationship("DealScore", back_populates="deal", cascade="all, delete-orphan")
    price_histories = relationship("PriceHistory", back_populates="deal", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the deal."""
        return f"<Deal {self.title} ({self.price} {self.currency})>"

class PriceHistory(Base):
    """Price history database model."""
    __tablename__ = "price_histories"
    __table_args__ = (
        UniqueConstraint('deal_id', 'timestamp', name='uq_price_history_deal_time'),
        CheckConstraint('price > 0', name='ch_positive_historical_price'),
        Index('ix_price_histories_deal_time', 'deal_id', 'timestamp'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    market_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"))
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(50))
    price_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # Relationships
    deal = relationship("Deal", back_populates="price_histories")
    market = relationship("Market", back_populates="price_histories")

    def __repr__(self) -> str:
        """String representation of the price history entry."""
        return f"<PriceHistory {self.price} {self.currency} at {self.timestamp}>"
