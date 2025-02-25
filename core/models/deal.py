"""Deal model module.

This module defines the deal-related models for the AI Agentic Deals System,
including deal status tracking, scoring, and price history.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
from uuid import UUID, uuid4
from decimal import Decimal
from pydantic import BaseModel, HttpUrl, Field, field_validator, conint, confloat
import enum
import re

from sqlalchemy import (
    ForeignKey, String, Text, DECIMAL, JSON, Enum as SQLAlchemyEnum,
    UniqueConstraint, CheckConstraint, Index, Column, DateTime, Boolean, event
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, Mapper
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import expression, text
from sqlalchemy.engine import Connection

from core.models.base import Base
from core.models.enums import (
    DealStatus, DealSource, MarketCategory, Currency
)
from core.exceptions.deal_exceptions import DealValidationError

class DealPriority(int, enum.Enum):
    """Deal priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class DealSearch(BaseModel):
    """Deal search parameters."""
    query: Optional[str] = None
    category: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    source: Optional[str] = None
    sort_by: Optional[str] = "relevance"
    sort_order: Optional[str] = "desc"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator('max_price')
    @classmethod
    def validate_max_price(cls, v, values):
        """Validate max_price is greater than min_price."""
        if v is not None and values.get('min_price') is not None:
            if v < values['min_price']:
                raise ValueError("max_price must be greater than min_price")
        return v

class DealFilter(BaseModel):
    """Deal filter parameters."""
    category: Optional[str] = None
    price_min: Optional[float] = Field(None, ge=0)
    price_max: Optional[float] = Field(None, ge=0)
    source: Optional[str] = None
    sort_by: Optional[str] = "relevance"
    sort_order: Optional[str] = "desc"

class PriceHistoryBase(BaseModel):
    """Base model for price history."""
    price: Decimal
    currency: str
    timestamp: datetime
    source: str
    meta_data: Optional[Dict[str, Any]] = None

class PriceHistory(Base):
    """SQLAlchemy model for price history."""
    __tablename__ = "price_histories"
    __table_args__ = (
        UniqueConstraint('deal_id', 'timestamp', name='uq_price_history_deal_time'),
        CheckConstraint('price > 0', name='ch_positive_historical_price'),
        Index('ix_price_histories_deal_time', 'deal_id', 'timestamp'),
        Index('ix_price_histories_market', 'market_id'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    market_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"))
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deal = relationship("Deal", back_populates="price_histories")
    market = relationship("Market", back_populates="price_histories")

    def __repr__(self) -> str:
        """String representation of the price history entry."""
        return "<PriceHistory {} {} at {}>".format(self.price, self.currency, self.timestamp)

class PriceHistoryResponse(PriceHistoryBase):
    """Response model for price history."""
    id: UUID
    deal_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }

class AIAnalysis(BaseModel):
    """AI analysis of a deal."""
    score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    price_trend: str
    price_prediction: Decimal
    recommendations: List[str]
    meta_data: Optional[Dict[str, Any]] = None

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

    @field_validator('original_price')
    @classmethod
    def validate_original_price(cls, v: Optional[Decimal], values: Dict[str, Any]) -> Optional[Decimal]:
        """Validate original price is greater than current price."""
        if v is not None and 'price' in values and v <= values['price']:
            raise ValueError("Original price must be greater than current price")
        return v

    @field_validator('expires_at')
    @classmethod
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

    @field_validator('original_price')
    @classmethod
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
    market_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Market analysis data including price trends and comparisons"
    )
    deal_score: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Overall deal score based on multiple factors"
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }

class Deal(Base):
    """Deal database model."""
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint('url', 'goal_id', name='uq_deal_url_goal'),
        CheckConstraint('price > 0', name='ch_positive_price'),
        CheckConstraint(
            'original_price IS NULL OR original_price > price',
            'ch_original_price_gt_price'
        ),
        Index('ix_deals_status_found', 'status', 'found_at'),
        Index('ix_deals_goal_status', 'goal_id', 'status'),
        Index('ix_deals_market_status', 'market_id', 'status'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=True)
    market_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    original_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    source: Mapped[DealSource] = mapped_column(
        SQLAlchemyEnum(DealSource, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[MarketCategory] = mapped_column(
        SQLAlchemyEnum(MarketCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    seller_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    availability: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[DealStatus] = mapped_column(
        SQLAlchemyEnum(DealStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DealStatus.ACTIVE
    )
    deal_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    price_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("TIMEZONE('UTC', CURRENT_TIMESTAMP)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("TIMEZONE('UTC', CURRENT_TIMESTAMP)")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    user = relationship("User", back_populates="deals")
    goal = relationship("Goal", back_populates="deals")
    market = relationship("Market", back_populates="deals")
    price_points = relationship("PricePoint", back_populates="deal", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="deal", cascade="all, delete-orphan")
    scores = relationship("DealScore", back_populates="deal", cascade="all, delete-orphan")
    trackers = relationship("TrackedDeal", back_populates="deal", cascade="all, delete-orphan")
    goal_matches = relationship("DealMatch", back_populates="deal", cascade="all, delete-orphan")
    tracked_by_users = relationship("TrackedDeal", back_populates="deal", cascade="all, delete-orphan")

    def __init__(
        self,
        *,
        user_id: Optional[UUID] = None,
        market_id: Optional[UUID] = None,
        goal_id: Optional[UUID] = None,
        user: Any = None,
        market: Any = None,
        goal: Any = None,
        title: str = None,
        description: Optional[str] = None,
        url: str = None,
        price: Decimal = None,
        original_price: Decimal = None,
        currency: str = "USD",
        source: DealSource = None,
        image_url: str = None,
        category: MarketCategory = None,
        seller_info: Dict[str, Any] = None,
        availability: Dict[str, Any] = None,
        found_at: datetime = None,
        expires_at: datetime = None,
        status: DealStatus = DealStatus.ACTIVE,
        deal_metadata: Dict[str, Any] = None,
        price_metadata: Dict[str, Any] = None,
        _skip_updated_at: bool = False,
        **kw,
    ):
        # Handle user parameter from factory
        if user is not None and hasattr(user, 'id'):
            user_id = user.id
        if user_id is None:
            raise ValueError("user_id is required")

        # Handle market parameter from factory
        if market is not None and hasattr(market, 'id'):
            market_id = market.id
        if market_id is None:
            raise ValueError("market_id is required")
            
        # Handle goal parameter from factory
        if goal is not None and hasattr(goal, 'id'):
            goal_id = goal.id

        if title is None:
            # Set a default title if none is provided
            title = f"Deal for {category.value if category else 'item'}"

        if url is None:
            # Set a default URL if none is provided
            url = "https://example.com/deal"

        if price is None:
            # Set a default price if none is provided
            price = Decimal("9.99")
            
        if source is None:
            # Set a default source if none is provided
            source = DealSource.MANUAL

        # Validate source
        if isinstance(source, str):
            try:
                source = DealSource(source.lower())
            except ValueError:
                raise ValueError(f"Invalid source: {source}")

        # Validate category
        if isinstance(category, str):
            try:
                category = MarketCategory(category.lower())
            except ValueError:
                raise ValueError(f"Invalid category: {category}")

        # Validate currency
        if currency and len(currency) > 3:
            raise ValueError("Currency code should be 3 characters or fewer")

        # Validate seller_info
        if seller_info is not None and not isinstance(seller_info, dict):
            raise ValueError("seller_info must be a dictionary")

        # Validate URL
        if not url:
            raise ValueError("URL is required")

        self.found_at = found_at or datetime.utcnow()
        self.expires_at = expires_at or datetime.utcnow() + timedelta(days=30)

        # Set the _skip_updated_at attribute directly instead of passing to super().__init__
        self._skip_updated_at = _skip_updated_at

        super().__init__(
            user_id=user_id,
            market_id=market_id,
            url=url,
            goal_id=goal_id,
            title=title,
            description=description,
            price=price,
            original_price=original_price,
            currency=currency,
            source=source,
            image_url=image_url,
            category=category,
            seller_info=seller_info,
            availability=availability,
            status=status,
            deal_metadata=deal_metadata or {},
            price_metadata=price_metadata or {},
            **kw,
        )

    def __setattr__(self, key, value):
        """Custom __setattr__ to handle specific validations"""
        if key == "title" and value is None:
            # Prevent setting title to None
            value = f"Deal for {self.category.value if hasattr(self, 'category') and self.category else 'item'}"
        elif key == "url" and value is None:
            # Prevent setting url to None
            value = "https://example.com/deal"
        elif key == "price" and value is None:
            # Prevent setting price to None
            value = Decimal("9.99")
        elif key == "source" and value is None:
            # Prevent setting source to None
            value = DealSource.MANUAL
        elif key == "status" and value is not None:
            # Validate status values
            if isinstance(value, DealStatus):
                # Value is already a valid enum
                pass
            elif isinstance(value, str):
                # Check if the string is a valid enum value
                valid_values = [status.value for status in DealStatus]
                if value not in valid_values:
                    raise ValueError(f"Invalid status: {value}. Valid values are {valid_values}")
        
        super().__setattr__(key, value)

    def _validate_url(self, url: str) -> None:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if not url_pattern.match(url):
            raise DealValidationError("Invalid URL format")

    def _validate_seller_info(self, seller_info: Dict[str, Any]) -> None:
        """Validate seller info format."""
        required_fields = {'name', 'rating'}
        if not isinstance(seller_info, dict):
            raise DealValidationError("Invalid seller info format")
        if not all(field in seller_info for field in required_fields):
            raise DealValidationError("Missing required seller info fields")
        if not isinstance(seller_info.get('rating'), (int, float)) or not 0 <= seller_info['rating'] <= 5:
            raise DealValidationError("Invalid seller rating")

    def __repr__(self) -> str:
        """String representation of the deal."""
        return "<Deal {} ({} {})>".format(self.title, self.price, self.currency)

@event.listens_for(Deal, 'before_update')
def receive_before_update(mapper: Mapper, connection: Connection, target: Deal) -> None:
    """Handle before update event."""
    # Only update the timestamp if it hasn't been explicitly set
    if not hasattr(target, '_skip_updated_at') or not target._skip_updated_at:
        target.updated_at = datetime.now(timezone.utc)

class DealAnalysis(BaseModel):
    deal_id: UUID
    score: float = Field(..., ge=0, le=100)
    metrics: Dict[str, float]
    analysis_timestamp: str
    confidence: float = Field(..., ge=0, le=1)
    anomaly_score: Optional[float] = Field(None, ge=0, le=1)
    recommendations: List[str]
    
    class Config:
        from_attributes = True

class DealSearchFilters(BaseModel):
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    categories: Optional[List[str]] = None
    brands: Optional[List[str]] = None
    condition: Optional[List[str]] = None
    sort_by: Optional[str] = Field(None, pattern="^(price_asc|price_desc|rating|expiry|relevance)$")
    
    @field_validator("max_price")
    @classmethod
    def validate_price_range(cls, v, values):
        if v is not None and "min_price" in values and values["min_price"] is not None:
            if v < values["min_price"]:
                raise ValueError("max_price must be greater than min_price")
        return v

class DealAnalytics(BaseModel):
    """Model for deal analytics"""
    deal_id: UUID
    price_history: List[Dict[str, Any]]
    price_trend: str
    market_analysis: Dict[str, Any]
    source_reliability: float
    score_history: List[Dict[str, Any]]
    created_at: datetime

class DealRecommendation(BaseModel):
    """Model for deal recommendations"""
    deal_id: UUID
    title: str
    price: Decimal
    original_price: Optional[Decimal]
    currency: str
    source: str
    url: str
    image_url: Optional[str]
    score: float
    reason: str
    expires_at: Optional[datetime]

class DealHistory(BaseModel):
    """Model for deal history"""
    deal_id: UUID
    price: Decimal
    original_price: Optional[Decimal]
    currency: str
    status: DealStatus
    metadata: Optional[Dict[str, Any]]
    timestamp: datetime

class DealPriceHistory(BaseModel):
    """Model for deal price history"""
    deal_id: UUID
    prices: List[Dict[str, Any]]
    trend: str
    average_price: Decimal
    lowest_price: Decimal
    highest_price: Decimal
    start_date: datetime
    end_date: datetime
