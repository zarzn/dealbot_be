"""Deal score model module.

This module defines the deal scoring models for the AI Agentic Deals System.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import logging
import json
from enum import Enum

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

class ScoreType(str, Enum):
    """Score type enumeration."""
    AI = "ai"
    USER = "user"
    SYSTEM = "system"
    COMBINED = "combined"
    MARKET = "market"

class DealMatch(Base):
    """Model for matching deals to goals."""
    __tablename__ = "deal_matches"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    goal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"))
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_criteria: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=expression.text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=expression.text("CURRENT_TIMESTAMP"))

    # Relationships
    goal = relationship("Goal", back_populates="matched_deals")
    deal = relationship("Deal", back_populates="goal_matches")

    def __repr__(self) -> str:
        """String representation."""
        return f"<DealMatch goal_id={self.goal_id} deal_id={self.deal_id} score={self.match_score}>"

class DealScore(Base):
    """Deal score database model."""
    __tablename__ = "deal_scores"
    __table_args__ = (
        CheckConstraint('score >= 0 AND score <= 1', name='ch_score_range'),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='ch_confidence_range'),
        Index('ix_deal_scores_deal_id', 'deal_id'),
        Index('ix_deal_scores_created_at', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    score_type: Mapped[str] = mapped_column(String(50), nullable=False, default="ai")
    score_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    factors: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deal = relationship("Deal", back_populates="scores")

    def __repr__(self) -> str:
        """String representation of the deal score."""
        return f"<DealScore {self.score}>"

    def to_json(self) -> str:
        """Convert deal score to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'deal_id': str(self.deal_id),
            'user_id': str(self.user_id),
            'score': float(self.score),
            'confidence': float(self.confidence),
            'timestamp': self.created_at.isoformat(),
            'factors': self.factors,
            'created_at': self.created_at.isoformat()
        })

    @classmethod
    async def create_score(
        cls,
        db: AsyncSession,
        deal_id: UUID,
        user_id: UUID,
        score: float,
        confidence: float = 1.0,
        factors: Optional[Dict[str, Any]] = None
    ) -> 'DealScore':
        """Create a new deal score."""
        try:
            if not 0 <= score <= 1:
                raise ValidationError("Score must be between 0 and 1")
            if not 0 <= confidence <= 1:
                raise ValidationError("Confidence must be between 0 and 1")

            score_obj = cls(
                deal_id=deal_id,
                user_id=user_id,
                score=score,
                confidence=confidence,
                factors=factors
            )
            db.add(score_obj)
            await db.commit()
            await db.refresh(score_obj)

            logger.info(
                "Created new deal score",
                extra={
                    'deal_id': str(deal_id),
                    'user_id': str(user_id),
                    'score': score,
                    'confidence': confidence
                }
            )
            return score_obj

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create deal score",
                extra={
                    'deal_id': str(deal_id),
                    'user_id': str(user_id),
                    'score': score,
                    'error': str(e)
                }
            )
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(str(e))

    async def update_metrics(
        self,
        db: AsyncSession,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update the score metrics."""
        try:
            if metrics is not None:
                self.factors = metrics

            await db.commit()
            logger.info(
                f"Updated metrics for deal score {self.id}",
                extra={
                    'id': str(self.id),
                    'deal_id': str(self.deal_id),
                    'factors': self.factors
                }
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to update metrics for deal score {self.id}: {str(e)}",
                extra={
                    'id': str(self.id),
                    'deal_id': str(self.deal_id),
                    'error': str(e)
                }
            )
            raise

# Pydantic models for API
class DealScoreCreate(BaseModel):
    """Deal score creation model."""

    deal_id: UUID
    user_id: UUID
    score: confloat(ge=0, le=1)
    confidence: confloat(ge=0, le=1) = 1.0
    timestamp: datetime
    factors: Dict[str, Any]
    created_at: datetime

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
    factors: Dict[str, Any]
    created_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: float
        }
