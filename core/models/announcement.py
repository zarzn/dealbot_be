"""Announcement models for system-wide notifications."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import String, Text, Boolean, DateTime, Column, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import text

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.models.base import Base


class AnnouncementType(str, Enum):
    """Types of system announcements."""
    FEATURE = "feature"
    MAINTENANCE = "maintenance"
    PROMOTION = "promotion"
    NEWS = "news"
    OTHER = "other"


class AnnouncementStatus(str, Enum):
    """Status of system announcements."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AnnouncementBase(BaseModel):
    """Base model for system announcements."""
    title: str = Field(..., description="Announcement title")
    content: str = Field(..., description="Announcement content")
    type: AnnouncementType = Field(..., description="Type of announcement")
    status: AnnouncementStatus = Field(default=AnnouncementStatus.DRAFT, description="Status of announcement")
    is_important: bool = Field(default=False, description="Whether this is an important announcement")
    publish_at: Optional[datetime] = Field(None, description="When to publish the announcement")
    expire_at: Optional[datetime] = Field(None, description="When the announcement expires")
    target_user_groups: List[str] = Field(default_factory=list, description="User groups to target")
    announcement_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    action_url: Optional[str] = Field(None, description="URL for action button")
    action_text: Optional[str] = Field(None, description="Text for action button")
    
    @field_validator('publish_at')
    def validate_publish_at(cls, v, values):
        """Validate that publish_at is in the future if status is scheduled."""
        if v and values.data.get('status') == AnnouncementStatus.SCHEDULED and v < datetime.utcnow():
            raise ValueError("Scheduled announcements must have a future publish date")
        return v


class AnnouncementCreate(AnnouncementBase):
    """Model for creating a new announcement."""
    pass


class AnnouncementUpdate(BaseModel):
    """Model for updating an announcement."""
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[AnnouncementType] = None
    status: Optional[AnnouncementStatus] = None
    is_important: Optional[bool] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    target_user_groups: Optional[List[str]] = None
    announcement_metadata: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None
    action_text: Optional[str] = None


class AnnouncementResponse(AnnouncementBase):
    """Model for announcement response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    
    model_config = ConfigDict(from_attributes=True)


class Announcement(Base):
    """SQLAlchemy model for system announcements."""
    __tablename__ = "announcements"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AnnouncementStatus.DRAFT.value)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    target_user_groups: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    announcement_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    action_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"), nullable=False)
    
    # Define relationship to creator
    creator = relationship("User", back_populates="announcements") 