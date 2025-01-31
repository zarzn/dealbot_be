"""Market model module.

This module defines the market-related models for the AI Agentic Deals System,
including market types, statuses, and database models.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import logging

from pydantic import BaseModel, Field, validator, conint
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey,
    Integer, JSON, Enum as SQLAlchemyEnum, Text, Float,
    UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression
import enum

from backend.core.models.base import Base
from backend.core.exceptions import MarketError, ValidationError

logger = logging.getLogger(__name__)

class MarketType(str, enum.Enum):
    """Supported market types."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    TARGET = "target"
    BESTBUY = "bestbuy"

class MarketStatus(str, enum.Enum):
    """Market operational statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

class MarketCategory(str, enum.Enum):
    """Market category types."""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    HOME = "home"
    TOYS = "toys"
    BOOKS = "books"
    SPORTS = "sports"
    AUTOMOTIVE = "automotive"
    HEALTH = "health"
    GROCERY = "grocery"
    OTHER = "other"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[MarketType] = mapped_column(SQLAlchemyEnum(MarketType), nullable=False)
    status: Mapped[MarketStatus] = mapped_column(
        SQLAlchemyEnum(MarketStatus),
        nullable=False,
        default=MarketStatus.ACTIVE,
        server_default=MarketStatus.ACTIVE.value
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    api_credentials: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    supported_categories: Mapped[List[MarketCategory]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [c.value for c in MarketCategory]
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=expression.true()
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_successful_request: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.func.now(),
        onupdate=expression.func.now()
    )

    # Relationships
    deals = relationship("Deal", back_populates="market")
    price_histories = relationship("PriceHistory", back_populates="market")

    def __repr__(self) -> str:
        """String representation of the market."""
        return f"<Market {self.name} ({self.type})>"

    async def check_rate_limit(self, db) -> bool:
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
                f"Failed to check rate limit",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            return False

    async def record_request(
        self,
        db,
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
                
                if self.error_count >= settings.MARKET_ERROR_THRESHOLD:
                    self.status = MarketStatus.ERROR
                    
            # Update success rate
            self.success_rate = (self.total_requests - self.error_count) / self.total_requests
            
            # Check if rate limited
            if self.requests_today >= self.rate_limit:
                self.status = MarketStatus.RATE_LIMITED
                
            await db.commit()
            
            logger.info(
                f"Recorded market request",
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
                f"Failed to record market request",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            raise MarketError(f"Failed to record market request: {str(e)}")

    async def reset_error_state(self, db) -> None:
        """Reset market error state."""
        try:
            if self.status not in [MarketStatus.ERROR, MarketStatus.RATE_LIMITED]:
                raise MarketError("Market is not in error state")
                
            self.status = MarketStatus.ACTIVE
            self.error_count = 0
            self.last_error = None
            self.last_error_at = None
            
            if self.status == MarketStatus.RATE_LIMITED:
                self.requests_today = 0
                self.last_reset_at = datetime.utcnow()
                
            await db.commit()
            
            logger.info(
                f"Reset market error state",
                extra={'market_id': str(self.id)}
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to reset market error state",
                extra={
                    'market_id': str(self.id),
                    'error': str(e)
                }
            )
            if isinstance(e, MarketError):
                raise
            raise MarketError(f"Failed to reset market error state: {str(e)}")

    @classmethod
    async def get_available_markets(
        cls,
        db,
        market_type: Optional[MarketType] = None,
        category: Optional[MarketCategory] = None
    ) -> List['Market']:
        """Get available markets with optional filtering."""
        try:
            query = db.query(cls).filter(
                cls.is_active == True,
                cls.status == MarketStatus.ACTIVE
            )
            
            if market_type:
                query = query.filter(cls.type == market_type)
            if category:
                query = query.filter(cls.supported_categories.contains([category]))
                
            markets = await query.all()
            
            logger.info(
                f"Retrieved available markets",
                extra={
                    'count': len(markets),
                    'type': market_type.value if market_type else None,
                    'category': category.value if category else None
                }
            )
            return markets
            
        except Exception as e:
            logger.error(
                f"Failed to get available markets",
                extra={
                    'type': market_type.value if market_type else None,
                    'category': category.value if category else None,
                    'error': str(e)
                }
            )
            raise MarketError(f"Failed to get available markets: {str(e)}")

class MarketCreate(BaseModel):
    """Market creation model."""
    name: str = Field(..., min_length=1, max_length=255)
    type: MarketType
    description: Optional[str] = None
    api_credentials: Optional[Dict[str, Any]] = None
    rate_limit: conint(gt=0) = Field(default=100)
    supported_categories: List[MarketCategory] = Field(
        default_factory=lambda: [c for c in MarketCategory]
    )

    @validator('api_credentials')
    def validate_credentials(cls, v, values):
        """Validate API credentials based on market type."""
        if not v:
            return v
            
        market_type = values.get('type')
        if not market_type:
            return v
            
        required_fields = {
            MarketType.AMAZON: ['access_key', 'secret_key', 'partner_tag'],
            MarketType.WALMART: ['client_id', 'client_secret'],
            MarketType.EBAY: ['app_id', 'cert_id', 'dev_id'],
            MarketType.TARGET: ['api_key'],
            MarketType.BESTBUY: ['api_key']
        }
        
        missing = [f for f in required_fields[market_type] if f not in v]
        if missing:
            raise ValidationError(
                f"Missing required credentials for {market_type}: {', '.join(missing)}"
            )
            
        return v

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class MarketUpdate(BaseModel):
    """Market update model."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    api_credentials: Optional[Dict[str, Any]] = None
    rate_limit: Optional[conint(gt=0)] = None
    supported_categories: Optional[List[MarketCategory]] = None
    is_active: Optional[bool] = None
    status: Optional[MarketStatus] = None

    @validator('api_credentials')
    def validate_update_credentials(cls, v):
        """Validate API credentials update."""
        if not v:
            return v
            
        # Ensure no empty string values
        if any(not val for val in v.values()):
            raise ValidationError("API credentials cannot contain empty values")
            
        return v

    @validator('status')
    def validate_status_update(cls, v):
        """Validate status updates."""
        if v == MarketStatus.ACTIVE:
            # Additional validation could be added here
            pass
        return v

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class MarketResponse(BaseModel):
    """Market response model."""
    id: UUID
    name: str
    type: MarketType
    status: MarketStatus
    description: Optional[str]
    supported_categories: List[MarketCategory]
    is_active: bool
    rate_limit: int
    requests_today: int
    success_rate: float
    avg_response_time: float
    last_successful_request: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

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
        """Create stats from market instance."""
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
    
    def __init__(self, db):
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
                    'type': market.type.value
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
            market = await self.db.query(Market).filter(Market.id == market_id).first()
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
            if isinstance(e, MarketError):
                raise
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
                Market.type == market_type,
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
                Market.status == MarketStatus.ACTIVE
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
            market.status = MarketStatus.INACTIVE
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
            market.status = MarketStatus.ACTIVE
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