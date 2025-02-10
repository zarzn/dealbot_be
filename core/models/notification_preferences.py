"""Notification preferences model module.

This module defines the notification preferences model for users,
allowing them to customize their notification settings.
"""

from datetime import time
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, ForeignKey, String, Time, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.models.base import Base
from core.models.notification import NotificationChannel, NotificationType


class NotificationFrequency(str, Enum):
    """Notification frequency settings"""
    IMMEDIATE = "immediate"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class NotificationTimeWindow(BaseModel):
    """Time window for receiving notifications"""
    start_time: time = Field(default=time(9, 0))  # 9:00 AM
    end_time: time = Field(default=time(21, 0))  # 9:00 PM
    timezone: str = Field(default="UTC")


class NotificationPreferencesBase(BaseModel):
    """Base model for notification preferences"""
    enabled_channels: List[NotificationChannel] = Field(
        default=[NotificationChannel.IN_APP, NotificationChannel.EMAIL]
    )
    notification_frequency: Dict[NotificationType, NotificationFrequency] = Field(
        default_factory=lambda: {
            NotificationType.DEAL_MATCH: NotificationFrequency.IMMEDIATE,
            NotificationType.GOAL_COMPLETED: NotificationFrequency.IMMEDIATE,
            NotificationType.GOAL_EXPIRED: NotificationFrequency.DAILY,
            NotificationType.PRICE_DROP: NotificationFrequency.IMMEDIATE,
            NotificationType.TOKEN_LOW: NotificationFrequency.DAILY,
            NotificationType.SYSTEM: NotificationFrequency.IMMEDIATE,
            NotificationType.CUSTOM: NotificationFrequency.IMMEDIATE
        }
    )
    time_windows: Dict[NotificationChannel, NotificationTimeWindow] = Field(
        default_factory=lambda: {
            channel: NotificationTimeWindow() for channel in NotificationChannel
        }
    )
    muted_until: Optional[time] = None
    do_not_disturb: bool = Field(default=False)
    email_digest: bool = Field(default=True)
    push_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=False)
    telegram_enabled: bool = Field(default=False)
    discord_enabled: bool = Field(default=False)
    minimum_priority: str = Field(default="low")


class NotificationPreferencesCreate(NotificationPreferencesBase):
    """Schema for creating notification preferences"""
    user_id: UUID


class NotificationPreferencesUpdate(NotificationPreferencesBase):
    """Schema for updating notification preferences"""
    pass


class NotificationPreferencesResponse(NotificationPreferencesBase):
    """Schema for notification preferences response"""
    id: UUID
    user_id: UUID

    class Config:
        """Pydantic model configuration"""
        from_attributes = True


class NotificationPreferences(Base):
    """Notification preferences database model"""
    __tablename__ = "notification_preferences"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    enabled_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value]
    )
    notification_frequency: Mapped[Dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            NotificationType.DEAL_MATCH.value: NotificationFrequency.IMMEDIATE.value,
            NotificationType.GOAL_COMPLETED.value: NotificationFrequency.IMMEDIATE.value,
            NotificationType.GOAL_EXPIRED.value: NotificationFrequency.DAILY.value,
            NotificationType.PRICE_DROP.value: NotificationFrequency.IMMEDIATE.value,
            NotificationType.TOKEN_LOW.value: NotificationFrequency.DAILY.value,
            NotificationType.SYSTEM.value: NotificationFrequency.IMMEDIATE.value,
            NotificationType.CUSTOM.value: NotificationFrequency.IMMEDIATE.value
        }
    )
    time_windows: Mapped[Dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            channel.value: {
                "start_time": "09:00",
                "end_time": "21:00",
                "timezone": "UTC"
            } for channel in NotificationChannel
        }
    )
    muted_until: Mapped[Optional[time]] = mapped_column(Time(timezone=True), nullable=True)
    do_not_disturb: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discord_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_priority: Mapped[str] = mapped_column(String(10), nullable=False, default="low")

    # Relationships
    user = relationship("User", back_populates="notification_preferences")

    def to_dict(self) -> Dict:
        """Convert notification preferences to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "enabled_channels": self.enabled_channels,
            "notification_frequency": self.notification_frequency,
            "time_windows": self.time_windows,
            "muted_until": self.muted_until.isoformat() if self.muted_until else None,
            "do_not_disturb": self.do_not_disturb,
            "email_digest": self.email_digest,
            "push_enabled": self.push_enabled,
            "sms_enabled": self.sms_enabled,
            "telegram_enabled": self.telegram_enabled,
            "discord_enabled": self.discord_enabled,
            "minimum_priority": self.minimum_priority
        } 