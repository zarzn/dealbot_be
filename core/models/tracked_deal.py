"""TrackedDeal model for tracking deals."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, ForeignKey, Boolean, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from .base import Base
from .enums import DealStatus

class TrackedDeal(Base):
    """Model for tracking deals."""
    
    __tablename__ = "tracked_deals"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    deal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default=DealStatus.ACTIVE.value)
    tracking_started: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_price: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_price_drop: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_availability: Mapped[bool] = mapped_column(Boolean, default=True)
    price_threshold: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2), nullable=True)
    tracking_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tracked_deals")
    deal = relationship("Deal", back_populates="trackers")

    def __repr__(self) -> str:
        """String representation."""
        return f"<TrackedDeal {self.id}: {self.deal_id} by {self.user_id}>" 