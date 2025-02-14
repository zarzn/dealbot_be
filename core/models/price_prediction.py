"""Price prediction models."""

from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID
from decimal import Decimal

from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, Field

from core.models.base import Base
from core.models.deal import Deal
from core.models.user import User

class PricePrediction(Base):
    """SQLAlchemy model for price predictions."""
    __tablename__ = "price_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_name: Mapped[str] = mapped_column(String, index=True)
    prediction_days: Mapped[int] = mapped_column(Integer, server_default="7")
    confidence_threshold: Mapped[float] = mapped_column(Float, server_default="0.8")
    predictions: Mapped[Dict] = mapped_column(JSONB)
    overall_confidence: Mapped[float] = mapped_column(Float)
    trend_direction: Mapped[Optional[str]] = mapped_column(String)
    trend_strength: Mapped[Optional[float]] = mapped_column(Float)
    seasonality_score: Mapped[Optional[float]] = mapped_column(Float)
    features_used: Mapped[Optional[Dict]] = mapped_column(JSONB)
    model_params: Mapped[Optional[Dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    meta_data: Mapped[Optional[Dict]] = mapped_column(JSONB)

    # Relationships
    deal = relationship("Deal", back_populates="price_predictions")
    user = relationship("User", back_populates="price_predictions")

class ModelMetrics(Base):
    """SQLAlchemy model for model metrics."""
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String, index=True)
    accuracy: Mapped[float] = mapped_column(Float)
    mae: Mapped[float] = mapped_column(Float)
    mse: Mapped[float] = mapped_column(Float)
    rmse: Mapped[float] = mapped_column(Float)
    mape: Mapped[float] = mapped_column(Float)
    r2_score: Mapped[float] = mapped_column(Float)
    training_time: Mapped[Optional[float]] = mapped_column(Float)
    prediction_time: Mapped[Optional[float]] = mapped_column(Float)
    last_retrain: Mapped[datetime] = mapped_column(DateTime)
    feature_importance: Mapped[Optional[Dict]] = mapped_column(JSONB)
    meta_data: Mapped[Optional[Dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

class PricePredictionBase(BaseModel):
    """Base model for price predictions."""
    deal_id: UUID
    prediction_days: int = Field(ge=1, le=90, default=7)
    confidence_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    model_params: Optional[Dict] = None
    metadata: Optional[Dict] = None

class PricePredictionCreate(PricePredictionBase):
    """Schema for creating a price prediction."""
    pass

class PricePredictionPoint(BaseModel):
    """Schema for a single prediction point."""
    date: datetime
    price: Decimal
    confidence: float
    lower_bound: Decimal
    upper_bound: Decimal

class PricePredictionResponse(PricePredictionBase):
    """Schema for price prediction response."""
    id: int
    predictions: List[PricePredictionPoint]
    model_name: str
    created_at: datetime
    overall_confidence: float
    trend_direction: str
    trend_strength: float
    seasonality_score: Optional[float] = None
    features_used: List[str]
    metadata: Optional[Dict] = None

    class Config:
        from_attributes = True

class PriceAnalysis(BaseModel):
    """Schema for price analysis."""
    trend: Dict[str, float]
    seasonality: Dict[str, float]
    anomalies: List[Dict[str, float]]
    forecast_quality: float
    price_drivers: List[Dict[str, float]]
    market_correlation: float
    volatility_index: float
    confidence_metrics: Dict[str, float]
    metadata: Optional[Dict] = None

class ModelPerformance(BaseModel):
    """Schema for model performance metrics."""
    model_name: str
    accuracy: float
    mae: float  # Mean Absolute Error
    mse: float  # Mean Squared Error
    rmse: float  # Root Mean Squared Error
    mape: float  # Mean Absolute Percentage Error
    r2_score: float
    training_time: float
    prediction_time: float
    last_retrain: datetime
    feature_importance: Dict[str, float]
    metadata: Optional[Dict] = None

class PriceTrend(BaseModel):
    """Schema for price trend analysis."""
    period: str
    trend_type: str
    strength: float
    support_price: Optional[Decimal] = None
    resistance_price: Optional[Decimal] = None
    breakout_probability: float
    volume_impact: float
    confidence: float
    metadata: Optional[Dict] = None 