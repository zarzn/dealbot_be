"""Deal score model module.

This module defines the deal score model for the AI Agentic Deals System,
including score calculation, analysis, and trend detection.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import logging

from pydantic import BaseModel, Field, validator, confloat
from sqlalchemy import (
    Column, Float, Boolean, DateTime, ForeignKey, Index,
    CheckConstraint, String, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression

from backend.core.models.base import Base
from backend.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class DealScore(Base):
    """Model representing deal score analysis"""
    __tablename__ = "deal_scores"
    __table_args__ = (
        Index('ix_deal_scores_deal_time', 'deal_id', 'analysis_time'),
        CheckConstraint('score >= 0 AND score <= 1', name='ch_score_range'),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='ch_confidence_range'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.func.now()
    )
    moving_average: Mapped[Optional[float]] = mapped_column(Float)
    std_dev: Mapped[Optional[float]] = mapped_column(Float)
    volatility: Mapped[Optional[float]] = mapped_column(Float)
    trend: Mapped[Optional[float]] = mapped_column(Float)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    deal = relationship("Deal", back_populates="scores")

    def __repr__(self) -> str:
        """String representation of the deal score."""
        return f"<DealScore {self.score:.2f} (confidence: {self.confidence:.2f})>"

    def to_json(self) -> str:
        """Convert deal score to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'deal_id': str(self.deal_id),
            'score': float(self.score),
            'analysis_time': self.analysis_time.isoformat(),
            'moving_average': float(self.moving_average) if self.moving_average else None,
            'std_dev': float(self.std_dev) if self.std_dev else None,
            'volatility': float(self.volatility) if self.volatility else None,
            'trend': float(self.trend) if self.trend else None,
            'is_anomaly': self.is_anomaly,
            'confidence': float(self.confidence),
            'metrics': self.metrics,
            'analysis_version': self.analysis_version
        })

    @classmethod
    async def create_score(
        cls,
        db,
        deal_id: UUID,
        score: float,
        confidence: float = 1.0,
        metrics: Optional[Dict[str, Any]] = None
    ) -> 'DealScore':
        """Create a new deal score."""
        try:
            if not 0 <= score <= 1:
                raise ValidationError("Score must be between 0 and 1")
            if not 0 <= confidence <= 1:
                raise ValidationError("Confidence must be between 0 and 1")

            score_obj = cls(
                deal_id=deal_id,
                score=score,
                confidence=confidence,
                metrics=metrics
            )
            db.add(score_obj)
            await db.commit()
            await db.refresh(score_obj)

            logger.info(
                f"Created new deal score",
                extra={
                    'deal_id': str(deal_id),
                    'score': score,
                    'confidence': confidence
                }
            )
            return score_obj

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to create deal score",
                extra={
                    'deal_id': str(deal_id),
                    'score': score,
                    'error': str(e)
                }
            )
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to create deal score: {str(e)}")

    async def update_metrics(
        self,
        db,
        moving_average: Optional[float] = None,
        std_dev: Optional[float] = None,
        volatility: Optional[float] = None,
        trend: Optional[float] = None,
        is_anomaly: Optional[bool] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update score metrics."""
        try:
            if moving_average is not None:
                self.moving_average = moving_average
            if std_dev is not None:
                self.std_dev = std_dev
            if volatility is not None:
                self.volatility = volatility
            if trend is not None:
                self.trend = trend
            if is_anomaly is not None:
                self.is_anomaly = is_anomaly
            if metrics is not None:
                self.metrics = metrics

            await db.commit()
            await db.refresh(self)

            logger.info(
                f"Updated deal score metrics",
                extra={
                    'id': str(self.id),
                    'deal_id': str(self.deal_id),
                    'moving_average': self.moving_average,
                    'std_dev': self.std_dev,
                    'volatility': self.volatility,
                    'trend': self.trend,
                    'is_anomaly': self.is_anomaly
                }
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to update deal score metrics",
                extra={
                    'id': str(self.id),
                    'deal_id': str(self.deal_id),
                    'error': str(e)
                }
            )
            raise ValidationError(f"Failed to update deal score metrics: {str(e)}")

# Pydantic models for API
class DealScoreCreate(BaseModel):
    """Schema for creating a deal score."""
    deal_id: UUID
    score: confloat(ge=0, le=1)
    confidence: confloat(ge=0, le=1) = 1.0
    metrics: Optional[Dict[str, Any]] = None

    @validator('score')
    def validate_score(cls, v: float) -> float:
        """Validate score is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValidationError("Score must be between 0 and 1")
        return v

    @validator('confidence')
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValidationError("Confidence must be between 0 and 1")
        return v

class DealScoreUpdate(BaseModel):
    """Schema for updating a deal score."""
    moving_average: Optional[float] = None
    std_dev: Optional[float] = None
    volatility: Optional[float] = None
    trend: Optional[float] = None
    is_anomaly: Optional[bool] = None
    metrics: Optional[Dict[str, Any]] = None

class DealScoreResponse(BaseModel):
    """Schema for deal score response."""
    id: UUID
    deal_id: UUID
    score: float
    analysis_time: datetime
    moving_average: Optional[float]
    std_dev: Optional[float]
    volatility: Optional[float]
    trend: Optional[float]
    is_anomaly: bool
    confidence: float
    metrics: Optional[Dict[str, Any]]
    analysis_version: int

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: float
        }
