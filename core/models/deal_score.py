"""Deal score model module.

This module defines the deal scoring models for the AI Agentic Deals System.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import logging
import json

from pydantic import BaseModel, Field, validator, confloat
from sqlalchemy import (
    Column, Float, Boolean, DateTime, ForeignKey, Index,
    CheckConstraint, String, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.base import Base
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class DealScore(Base):
    """Deal score database model."""
    __tablename__ = "deal_scores"
    __table_args__ = (
        CheckConstraint('score >= 0 AND score <= 1', name='ch_score_range'),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='ch_confidence_range'),
        Index('ix_deal_scores_deal_id', 'deal_id'),
        Index('ix_deal_scores_timestamp', 'timestamp'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    score_type: Mapped[str] = mapped_column(String(50), default="ai")
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    deal = relationship("Deal", back_populates="scores")

    def __repr__(self) -> str:
        """String representation of the deal score."""
        return f"<DealScore {self.score} ({self.score_type})>"

    def to_json(self) -> str:
        """Convert deal score to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'deal_id': str(self.deal_id),
            'score': float(self.score),
            'confidence': float(self.confidence),
            'timestamp': self.timestamp.isoformat(),
            'score_type': self.score_type,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        })

    @classmethod
    async def create_score(
        cls,
        db: AsyncSession,
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
                metadata=metrics
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
        db: AsyncSession,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update score metrics."""
        try:
            if metrics is not None:
                self.metadata = metrics

            await db.commit()
            await db.refresh(self)

            logger.info(
                f"Updated deal score metrics",
                extra={
                    'id': str(self.id),
                    'deal_id': str(self.deal_id),
                    'metadata': self.metadata
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

    @classmethod
    def validate_score(cls, score: float) -> float:
        """Validate score is between 0 and 1."""
        if not 0 <= score <= 1:
            raise ValidationError("Score must be between 0 and 1")
        return score

    @classmethod
    def validate_confidence(cls, confidence: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0 <= confidence <= 1:
            raise ValidationError("Confidence must be between 0 and 1")
        return confidence

class DealScoreUpdate(BaseModel):
    """Schema for updating a deal score."""
    metrics: Optional[Dict[str, Any]] = None

class DealScoreResponse(BaseModel):
    """Schema for deal score response."""
    id: UUID
    deal_id: UUID
    score: float
    confidence: float
    timestamp: datetime
    score_type: str
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: float
        }
