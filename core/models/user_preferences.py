"""User and notification preferences models."""

from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from sqlalchemy import Column, ForeignKey, String, JSON, DateTime, Boolean, Time, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.database import Base
from core.models.notification import NotificationChannel, NotificationType

class Theme(str, Enum):
    """Theme options."""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

class Language(str, Enum):
    """Language options."""
    EN = "en"
    ES = "es"
    FR = "fr"

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

class UserPreferences(Base):
    """User preferences model."""
    __tablename__ = "user_preferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    theme: Mapped[str] = mapped_column(String, default=Theme.SYSTEM)
    language: Mapped[str] = mapped_column(String, default=Language.EN)
    timezone: Mapped[str] = mapped_column(String, default="UTC")
    
    # Notification preferences
    enabled_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value]
    )
    notification_frequency: Mapped[Dict] = mapped_column(
        JSONB,
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
        JSONB,
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
    
    # Alert settings
    deal_alert_settings: Mapped[Dict] = mapped_column(JSONB, default={})
    price_alert_settings: Mapped[Dict] = mapped_column(JSONB, default={})
    email_preferences: Mapped[Dict] = mapped_column(JSONB, default={})
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="preferences")

    def to_dict(self) -> Dict:
        """Convert preferences to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "theme": self.theme,
            "language": self.language,
            "timezone": self.timezone,
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
            "minimum_priority": self.minimum_priority,
            "deal_alert_settings": self.deal_alert_settings,
            "price_alert_settings": self.price_alert_settings,
            "email_preferences": self.email_preferences,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class UserPreferencesResponse(BaseModel):
    """User preferences response schema."""
    id: UUID
    user_id: UUID
    theme: Theme
    language: Language
    timezone: str
    enabled_channels: List[NotificationChannel]
    notification_frequency: Dict[NotificationType, NotificationFrequency]
    time_windows: Dict[NotificationChannel, NotificationTimeWindow]
    muted_until: Optional[time]
    do_not_disturb: bool
    email_digest: bool
    push_enabled: bool
    sms_enabled: bool
    telegram_enabled: bool
    discord_enabled: bool
    minimum_priority: str
    deal_alert_settings: Dict
    price_alert_settings: Dict
    email_preferences: Dict
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True

class UserPreferencesUpdate(BaseModel):
    """User preferences update schema."""
    theme: Optional[Theme] = None
    language: Optional[Language] = None
    timezone: Optional[str] = None
    enabled_channels: Optional[List[NotificationChannel]] = None
    notification_frequency: Optional[Dict[NotificationType, NotificationFrequency]] = None
    time_windows: Optional[Dict[NotificationChannel, NotificationTimeWindow]] = None
    muted_until: Optional[time] = None
    do_not_disturb: Optional[bool] = None
    email_digest: Optional[bool] = None
    push_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    discord_enabled: Optional[bool] = None
    minimum_priority: Optional[str] = None
    deal_alert_settings: Optional[Dict] = None
    price_alert_settings: Optional[Dict] = None
    email_preferences: Optional[Dict] = None 