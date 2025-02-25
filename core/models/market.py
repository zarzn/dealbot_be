"""Market model module.

This module defines the market-related models for the AI Agentic Deals System,
including market types, statuses, and database models.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import logging
import enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import now

from pydantic import BaseModel, Field, validator, conint
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey,
    Integer, JSON, Enum as SQLAlchemyEnum, Text, Float,
    UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression, text, func
from sqlalchemy import select

from core.models.base import Base
from core.models.enums import MarketType, MarketStatus, MarketCategory
from core.exceptions import (
    MarketError,
    MarketValidationError,
    MarketNotFoundError,
    MarketConnectionError,
    MarketRateLimitError,
    MarketConfigurationError,
    MarketOperationError,
    ValidationError
)
from core.config import settings

logger = logging.getLogger(__name__)

# Constants
MARKET_ERROR_THRESHOLD = 10  # Default value if not set in settings

class Market(Base):
    """Market database model."""
    __tablename__ = "markets"
    __table_args__ = (
        UniqueConstraint('name', 'type', name='uq_market_name_type'),
        CheckConstraint('rate_limit > 0', name='ch_positive_rate_limit'),
        CheckConstraint('success_rate >= 0 AND success_rate <= 1', name='ch_success_rate_range'),
        Index('ix_markets_type_status', 'type', 'status'),
        Index('ix_markets_active', 'is_active'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        SQLAlchemyEnum(MarketType, values_callable=lambda x: [e.value.lower() for e in x], name="markettype"),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(255))
    api_key: Mapped[Optional[str]] = mapped_column(String(255))
    _status: Mapped[str] = mapped_column(
        'status',
        SQLAlchemyEnum(MarketStatus, values_callable=lambda x: [e.value.lower() for e in x], name="marketstatus"),
        nullable=False,
        default=MarketStatus.ACTIVE.value.lower()
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_successful_request: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=func.current_timestamp(),
        server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    deals = relationship("Deal", back_populates="market", cascade="all, delete-orphan")
    price_histories = relationship("PriceHistory", back_populates="market", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize market with validation."""
        if 'type' in kwargs:
            self.validate_type(kwargs['type'])
        if 'rate_limit' in kwargs:
            self.validate_rate_limit(kwargs['rate_limit'])
        if 'status' in kwargs:
            self.validate_status(kwargs['status'])
        super().__init__(**kwargs)

    @staticmethod
    def validate_type(market_type: str) -> None:
        """Validate market type."""
        valid_types = [market_type.value.lower() for market_type in MarketType]
        if isinstance(market_type, str) and market_type.lower() not in valid_types:
            raise ValueError(f"Invalid market type: {market_type}. Valid types are: {', '.join(valid_types)}")

    @staticmethod
    def validate_status(status: str) -> None:
        """Validate market status."""
        valid_statuses = [status.value.lower() for status in MarketStatus]
        if isinstance(status, str) and status.lower() not in valid_statuses:
            raise ValueError(f"Invalid market status: {status}. Valid statuses are: {', '.join(valid_statuses)}")

    @staticmethod
    def validate_rate_limit(rate_limit: int) -> None:
        """Validate rate limit."""
        if rate_limit <= 0:
            raise ValueError("Rate limit must be greater than 0")

    def __repr__(self) -> str:
        """String representation of the market."""
        return f"<Market {self.name} ({self.type})>"

    @property
    def status(self) -> str:
        """Get market status."""
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """Set market status with validation."""
        self.validate_status(value)
        self._status = value.lower()

    async def check_rate_limit(self, db: AsyncSession) -> bool:
        """Check if market has exceeded rate limit."""
        try:
            now = datetime.utcnow()
            
            # Reset daily counters if needed
            if self.last_reset_at.date() < now.date():
                self.requests_today = 0
                self.last_reset_at = now
                await db.commit()
                
            return self.requests_today < self.rate_limit
            
        except Exception as e:
            logger.error(
                "Failed to check rate limit",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            await db.rollback()
            return False

    async def record_request(
        self,
        db: AsyncSession,
        success: bool,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Record API request result."""
        try:
            self.total_requests += 1
            self.requests_today += 1
            
            if success:
                self.last_successful_request = datetime.utcnow()
                if response_time is not None:
                    # Update moving average of response time
                    self.avg_response_time = (
                        (self.avg_response_time * (self.total_requests - 1) + response_time)
                        / self.total_requests
                    )
            else:
                self.error_count += 1
                self.last_error = error
                self.last_error_at = datetime.utcnow()
                
                error_threshold = getattr(settings, 'MARKET_ERROR_THRESHOLD', MARKET_ERROR_THRESHOLD)
                if self.error_count >= error_threshold:
                    self.status = MarketStatus.ERROR.value
                    
            # Update success rate
            self.success_rate = (self.total_requests - self.error_count) / self.total_requests
            
            # Check if rate limited
            if self.requests_today >= self.rate_limit:
                self.status = MarketStatus.RATE_LIMITED.value
                
            await db.commit()
            
            logger.info(
                "Recorded market request",
                extra={
                    'market_id': str(self.id),
                    'success': success,
                    'response_time': response_time,
                    'total_requests': self.total_requests,
                    'error_count': self.error_count
                }
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to record market request",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            raise ValidationError(f"Failed to record market request: {str(e)}")

    async def reset_error_state(self, db: AsyncSession) -> None:
        """Reset market error state."""
        try:
            if self.status not in [MarketStatus.ERROR.value, MarketStatus.RATE_LIMITED.value]:
                raise ValidationError("Market is not in error state")
                
            self.status = MarketStatus.ACTIVE.value
            self.error_count = 0
            self.last_error = None
            self.last_error_at = None
            
            if self.status == MarketStatus.RATE_LIMITED.value:
                self.requests_today = 0
                self.last_reset_at = datetime.utcnow()
                
            await db.commit()
            
            logger.info(
                "Reset market error state",
                extra={'market_id': str(self.id)}
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to reset market error state",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to reset market error state: {str(e)}")

    @classmethod
    async def get_available_markets(
        cls,
        db: AsyncSession,
        market_type: Optional[MarketType] = None,
        category: Optional[MarketCategory] = None
    ) -> List['Market']:
        """Get available markets with optional filtering."""
        try:
            query = select(cls).where(
                cls.is_active == True,
                cls.status == MarketStatus.ACTIVE.value
            )
            
            if market_type:
                query = query.where(cls.type == market_type.value)
                
            if category:
                query = query.where(cls.config['category'].astext == category.value)
                
            result = await db.execute(query)
            markets = result.scalars().all()
            
            logger.info(
                "Retrieved available markets",
                extra={
                    'count': len(markets),
                    'type': market_type.value if market_type else None,
                    'category': category.value if category else None
                }
            )
            return markets
            
        except Exception as e:
            logger.error(
                "Failed to get available markets",
                extra={
                    'type': market_type.value if market_type else None,
                    'category': category.value if category else None,
                    'error': str(e)
                }
            )
            raise ValidationError(f"Failed to get available markets: {str(e)}")

# Pydantic Models for API Operations

class MarketBase(BaseModel):
    """Base market model."""
    name: str = Field(..., min_length=1, max_length=100)
    type: MarketType
    description: Optional[str] = None
    api_endpoint: Optional[str] = None
    rate_limit: Optional[int] = Field(default=100, gt=0)
    config: Optional[Dict[str, Any]] = None

    @classmethod
    def validate_credentials(cls, credentials: Dict[str, str], market_type: MarketType) -> None:
        """Validate market-specific API credentials."""
        required_fields = {
            MarketType.AMAZON: ["access_key", "secret_key", "partner_tag"],
            MarketType.WALMART: ["client_id", "client_secret"],
            MarketType.EBAY: ["app_id", "cert_id", "dev_id"]
        }

        if market_type not in required_fields:
            raise ValidationError(f"Unsupported market type: {market_type}")

        missing_fields = [field for field in required_fields[market_type] 
                         if field not in credentials]
        
        if missing_fields:
            raise ValidationError(
                f"Missing required API credentials for {market_type}: {', '.join(missing_fields)}"
            )

    @classmethod
    def validate_update_credentials(cls, credentials: Dict[str, str], market_type: MarketType) -> None:
        """Validate credentials for update operation."""
        cls.validate_credentials(credentials, market_type)

    @classmethod
    def validate_status_update(cls, status: MarketStatus, current_status: MarketStatus) -> None:
        """Validate market status transition."""
        valid_transitions = {
            MarketStatus.ACTIVE: [MarketStatus.INACTIVE, MarketStatus.MAINTENANCE, MarketStatus.ERROR],
            MarketStatus.INACTIVE: [MarketStatus.ACTIVE],
            MarketStatus.MAINTENANCE: [MarketStatus.ACTIVE, MarketStatus.INACTIVE],
            MarketStatus.ERROR: [MarketStatus.ACTIVE, MarketStatus.MAINTENANCE],
            MarketStatus.RATE_LIMITED: [MarketStatus.ACTIVE]
        }

        if status not in valid_transitions.get(current_status, []):
            raise ValidationError(
                f"Invalid status transition from {current_status} to {status}"
            )

class MarketCreate(MarketBase):
    """Market creation model."""
    api_credentials: Optional[Dict[str, str]] = None

class MarketUpdate(BaseModel):
    """Market update model."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_credentials: Optional[Dict[str, str]] = None
    rate_limit: Optional[int] = Field(None, gt=0)
    config: Optional[Dict[str, Any]] = None
    status: Optional[MarketStatus] = None
    is_active: Optional[bool] = None

class MarketResponse(MarketBase):
    """Market response model."""
    id: UUID
    status: MarketStatus
    is_active: bool
    error_count: int
    requests_today: int
    total_requests: int
    success_rate: float
    avg_response_time: float
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    last_successful_request: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MarketCategoryInfo(BaseModel):
    """Market category information model."""
    id: str
    name: str
    parent_id: Optional[str] = None

class MarketAnalytics(BaseModel):
    """Market analytics model."""
    total_products: int
    active_deals: int
    average_discount: float
    top_categories: List[Dict[str, Any]]
    price_ranges: Dict[str, int]
    daily_stats: Dict[str, int]

class MarketMetrics(BaseModel):
    """Market performance metrics model."""
    total_products: int
    active_deals: int
    average_discount: float
    response_time: str
    success_rate: float

class MarketComparison(BaseModel):
    """Market comparison model."""
    comparison_date: str
    markets: List[Dict[str, Any]]
    summary: Dict[str, Optional[str]]

class MarketPriceHistory(BaseModel):
    """Market price history model."""
    market_id: UUID
    product_id: str
    price_points: List[Dict[str, Any]]
    average_price: float
    lowest_price: float
    highest_price: float
    price_trend: str

class MarketAvailability(BaseModel):
    """Market availability model."""
    market_id: UUID
    total_products: int
    available_products: int
    out_of_stock: int
    availability_rate: float
    last_checked: datetime

class MarketTrends(BaseModel):
    """Market trends model."""
    trend_period: str
    top_trending: List[Dict[str, Any]]
    price_trends: Dict[str, float]
    category_trends: List[Dict[str, Any]]
    search_trends: List[Dict[str, int]]

class MarketPerformance(BaseModel):
    """Market performance model."""
    market_id: UUID
    uptime: float
    response_times: Dict[str, float]
    error_rates: Dict[str, float]
    success_rates: Dict[str, float]
    api_usage: Dict[str, int]

class MarketStats(BaseModel):
    """Market statistics model."""
    total_requests: int
    success_rate: float
    avg_response_time: float
    error_count: int
    requests_today: int
    last_error: Optional[str]
    last_error_at: Optional[datetime]
    last_successful_request: Optional[datetime]

    @classmethod
    def from_market(cls, market: Market) -> 'MarketStats':
        """Create MarketStats from Market instance."""
        return cls(
            total_requests=market.total_requests,
            success_rate=market.success_rate,
            avg_response_time=market.avg_response_time,
            error_count=market.error_count,
            requests_today=market.requests_today,
            last_error=market.last_error,
            last_error_at=market.last_error_at,
            last_successful_request=market.last_successful_request
        )

class MarketRepository:
    """Repository for market operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize repository."""
        self.db = db
        
    async def create(self, market_data: MarketCreate) -> Market:
        """Create new market."""
        try:
            market = Market(**market_data.model_dump())
            self.db.add(market)
            await self.db.commit()
            await self.db.refresh(market)
            
            logger.info(
                f"Created new market",
                extra={
                    'market_id': str(market.id),
                    'type': market.type
                }
            )
            return market
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to create market",
                extra={'error': str(e)}
            )
            raise MarketError(f"Failed to create market: {str(e)}")
            
    async def update(self, market_id: UUID, market_data: MarketUpdate) -> Market:
        """Update existing market."""
        try:
            stmt = select(Market).where(Market.id == market_id)
            result = await self.db.execute(stmt)
            market = result.scalar_one_or_none()
            
            if not market:
                raise MarketError(f"Market {market_id} not found")
                
            update_data = market_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(market, key, value)
                
            await self.db.commit()
            await self.db.refresh(market)
            
            logger.info(
                f"Updated market",
                extra={
                    'market_id': str(market.id),
                    'updated_fields': list(update_data.keys())
                }
            )
            return market
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to update market",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            raise MarketError(f"Failed to update market: {str(e)}")
            
    async def get_stats(self, market_id: UUID) -> MarketStats:
        """Get market statistics."""
        try:
            market = await self.db.query(Market).filter(Market.id == market_id).first()
            if not market:
                raise MarketError(f"Market {market_id} not found")
                
            return MarketStats.from_market(market)
            
        except Exception as e:
            logger.error(
                f"Failed to get market stats",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to get market stats: {str(e)}")
            
    async def get_by_id(self, market_id: UUID) -> Market:
        """Get market by ID."""
        try:
            market = await self.db.query(Market).filter(Market.id == market_id).first()
            if not market:
                raise MarketError(f"Market {market_id} not found")
            return market
            
        except Exception as e:
            logger.error(
                f"Failed to get market",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to get market: {str(e)}")
            
    async def get_by_type(self, market_type: MarketType) -> List[Market]:
        """Get markets by type."""
        try:
            markets = await self.db.query(Market).filter(
                Market.type == market_type.value,
                Market.is_active == True
            ).all()
            
            logger.info(
                f"Retrieved markets by type",
                extra={
                    'type': market_type.value,
                    'count': len(markets)
                }
            )
            return markets
            
        except Exception as e:
            logger.error(
                f"Failed to get markets by type",
                extra={
                    'type': market_type.value,
                    'error': str(e)
                }
            )
            raise MarketError(f"Failed to get markets by type: {str(e)}")
            
    async def get_all_active(self) -> List[Market]:
        """Get all active markets."""
        try:
            markets = await self.db.query(Market).filter(
                Market.is_active == True,
                Market.status == MarketStatus.ACTIVE.value
            ).all()
            
            logger.info(
                f"Retrieved all active markets",
                extra={'count': len(markets)}
            )
            return markets
            
        except Exception as e:
            logger.error(
                f"Failed to get active markets",
                extra={'error': str(e)}
            )
            raise MarketError(f"Failed to get active markets: {str(e)}")
            
    async def deactivate(self, market_id: UUID) -> Market:
        """Deactivate market."""
        try:
            market = await self.get_by_id(market_id)
            market.is_active = False
            market.status = MarketStatus.INACTIVE.value
            await self.db.commit()
            
            logger.info(
                f"Deactivated market",
                extra={'market_id': str(market_id)}
            )
            return market
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to deactivate market",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to deactivate market: {str(e)}")
            
    async def reactivate(self, market_id: UUID) -> Market:
        """Reactivate market."""
        try:
            market = await self.get_by_id(market_id)
            market.is_active = True
            market.status = MarketStatus.ACTIVE.value
            market.error_count = 0
            market.last_error = None
            market.last_error_at = None
            await self.db.commit()
            
            logger.info(
                f"Reactivated market",
                extra={'market_id': str(market_id)}
            )
            return market
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to reactivate market",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to reactivate market: {str(e)}")
            
    async def update_credentials(
        self,
        market_id: UUID,
        credentials: Dict[str, Any]
    ) -> Market:
        """Update market API credentials."""
        try:
            market = await self.get_by_id(market_id)
            
            # Validate credentials for market type
            MarketCreate.validate_credentials(credentials, {'type': market.type})
            
            market.api_credentials = credentials
            await self.db.commit()
            
            logger.info(
                f"Updated market credentials",
                extra={'market_id': str(market_id)}
            )
            return market
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to update market credentials",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to update market credentials: {str(e)}")
            
    async def get_market_health(self, market_id: UUID) -> Dict[str, Any]:
        """Get market health metrics."""
        try:
            market = await self.get_by_id(market_id)
            stats = await self.get_stats(market_id)
            
            # Calculate health metrics
            health_status = "healthy"
            if market.error_count > settings.MARKET_ERROR_THRESHOLD:
                health_status = "unhealthy"
            elif market.success_rate < settings.MARKET_MIN_SUCCESS_RATE:
                health_status = "degraded"
                
            return {
                "status": health_status,
                "success_rate": stats.success_rate,
                "error_count": stats.error_count,
                "avg_response_time": stats.avg_response_time,
                "requests_today": stats.requests_today,
                "rate_limit_remaining": market.rate_limit - market.requests_today,
                "last_error": stats.last_error,
                "last_error_at": stats.last_error_at,
                "last_successful_request": stats.last_successful_request
            }
            
        except Exception as e:
            logger.error(
                f"Failed to get market health",
                extra={
                    'market_id': str(market_id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to get market health: {str(e)}")

# Remove duplicate enums since they are imported from enums.py 