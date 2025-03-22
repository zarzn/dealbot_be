"""Shared content models.

This module defines models for sharing deals and search results with other users.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, AnyUrl

from sqlalchemy import (
    ForeignKey, String, Text, Boolean, JSON, Enum as SQLAlchemyEnum,
    UniqueConstraint, CheckConstraint, Index, Column, DateTime, Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import expression, text

from core.models.base import Base


class ShareableContentType(str, Enum):
    """Types of shareable content."""
    DEAL = "deal"
    SEARCH_RESULTS = "search_results"
    COLLECTION = "collection"  # For future use: multiple deals grouped as a collection


class ShareVisibility(str, Enum):
    """Visibility settings for shared content."""
    PUBLIC = "public"  # Anyone with the link can view
    PRIVATE = "private"  # Only authenticated users with direct link can view


class SharedContent(Base):
    """SQLAlchemy model for shared content."""
    __tablename__ = "shared_contents"
    __table_args__ = (
        Index('ix_shared_contents_user', 'user_id'),
        Index('ix_shared_contents_created', 'created_at'),
        Index('ix_shared_contents_share_id', 'share_id', unique=True),
        Index('ix_shared_contents_expires', 'expires_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    share_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)  # Short ID for sharing URLs
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(
        SQLAlchemyEnum(ShareableContentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    content_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)  # For single deal sharing
    content_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)  # Stored snapshot of the content
    visibility: Mapped[str] = mapped_column(
        SQLAlchemyEnum(ShareVisibility, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ShareVisibility.PUBLIC.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("TIMEZONE('UTC', CURRENT_TIMESTAMP)")
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationships
    user = relationship("User", back_populates="shared_contents")
    share_views = relationship("ShareView", back_populates="shared_content", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SharedContent(id='{self.id}', share_id='{self.share_id}', type='{self.content_type}')>"


class ShareView(Base):
    """SQLAlchemy model for tracking views of shared content."""
    __tablename__ = "share_views"
    __table_args__ = (
        Index('ix_share_views_content', 'shared_content_id'),
        Index('ix_share_views_user', 'viewer_id'),
        Index('ix_share_views_timestamp', 'viewed_at'),
    )
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    shared_content_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("shared_contents.id", ondelete="CASCADE"))
    viewer_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    viewer_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 addresses can be up to 45 chars
    viewer_device: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("TIMEZONE('UTC', CURRENT_TIMESTAMP)")
    )
    referrer: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Relationships
    shared_content = relationship("SharedContent", back_populates="share_views")
    viewer = relationship("User", backref="viewed_shares")

    def __repr__(self) -> str:
        return f"<ShareView(id='{self.id}', content_id='{self.shared_content_id}', viewed_at='{self.viewed_at}')>"


# Pydantic models for API requests/responses

class ShareContentRequest(BaseModel):
    """Request model for sharing content."""
    content_type: ShareableContentType
    content_id: Optional[UUID] = None  # Required for single deal sharing
    search_params: Optional[Dict[str, Any]] = None  # Required for search results sharing
    title: Optional[str] = None
    description: Optional[str] = None
    expiration_days: Optional[int] = Field(None, ge=1, le=365)
    visibility: ShareVisibility = ShareVisibility.PUBLIC
    include_personal_notes: bool = False
    personal_notes: Optional[str] = None


class ShareContentResponse(BaseModel):
    """Response model for sharing content."""
    share_id: str
    title: str
    description: Optional[str] = None
    content_type: ShareableContentType
    shareable_link: str
    expiration_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SharedContentDetail(BaseModel):
    """Detailed response model for shared content."""
    share_id: str
    title: str
    description: Optional[str] = None
    content_type: ShareableContentType
    content: Dict[str, Any]
    created_by: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    view_count: int
    personal_notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class SharedContentMetrics(BaseModel):
    """Metrics for shared content."""
    share_id: str
    view_count: int
    unique_viewers: int
    referring_sites: Dict[str, int]
    viewer_devices: Dict[str, int]
    created_at: datetime
    last_viewed: Optional[datetime] = None
    
    class Config:
        from_attributes = True 