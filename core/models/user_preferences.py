"""User and notification preferences models."""

from datetime import datetime, time, timedelta
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from sqlalchemy import Column, ForeignKey, String, JSON, DateTime, Boolean, Time, ARRAY, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.models.base import Base
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
    DE = "de"

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
            NotificationType.DEAL: NotificationFrequency.IMMEDIATE,
            NotificationType.GOAL: NotificationFrequency.IMMEDIATE,
            NotificationType.PRICE_ALERT: NotificationFrequency.IMMEDIATE,
            NotificationType.TOKEN: NotificationFrequency.DAILY,
            NotificationType.SECURITY: NotificationFrequency.IMMEDIATE,
            NotificationType.MARKET: NotificationFrequency.DAILY,
            NotificationType.SYSTEM: NotificationFrequency.IMMEDIATE
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
    """User preferences SQLAlchemy model."""
    __tablename__ = "user_preferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        unique=True
    )
    theme: Mapped[str] = mapped_column(String, default=Theme.SYSTEM.value)
    language: Mapped[str] = mapped_column(String, default=Language.EN.value)
    timezone: Mapped[str] = mapped_column(String, default="UTC")
    
    # Notification preferences
    enabled_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default=text("ARRAY['in_app', 'email']")
    )
    notification_frequency: Mapped[Dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("""
            '{
                "deal": {"type": "deal", "frequency": "immediate"},
                "goal": {"type": "goal", "frequency": "immediate"},
                "price_alert": {"type": "price_alert", "frequency": "immediate"},
                "token": {"type": "token", "frequency": "daily"},
                "security": {"type": "security", "frequency": "immediate"},
                "market": {"type": "market", "frequency": "daily"},
                "system": {"type": "system", "frequency": "immediate"}
            }'::jsonb
        """)
    )
    time_windows: Mapped[Dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("""
            '{"in_app": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"},
              "email": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"}}'::jsonb
        """)
    )
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    do_not_disturb: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discord_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_priority: Mapped[str] = mapped_column(String(10), nullable=False, default="low")
    
    # Alert settings
    deal_alert_settings: Mapped[Dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    price_alert_settings: Mapped[Dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    email_preferences: Mapped[Dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )

    # Relationships
    user = relationship("User", back_populates="user_preferences", lazy="selectin")

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

    def is_in_time_window(self, channel: str, current_time: datetime) -> bool:
        """Check if the current time is within the notification time window for a channel.
        
        Args:
            channel: The notification channel to check
            current_time: The current time to check against
            
        Returns:
            bool: True if within time window, False otherwise
        """
        # If channel not configured, default to True
        if channel not in self.time_windows:
            return True
            
        window = self.time_windows[channel]
        window_start = time.fromisoformat(window["start_time"])
        window_end = time.fromisoformat(window["end_time"])
        timezone = window.get("timezone", "UTC")
        
        # Convert times to datetime objects on the same day for comparison
        from datetime import date
        today = date.today()
        
        # Adjust for timezone if needed
        from pytz import timezone as pytz_timezone
        from datetime import timezone as dt_timezone
        
        try:
            # Convert current_time to the timezone in the window settings
            if hasattr(current_time, "tzinfo") and current_time.tzinfo is not None:
                # If current_time already has timezone info
                tz = pytz_timezone(timezone)
                current_time = current_time.astimezone(tz)
            else:
                # If current_time has no timezone, assume it's in UTC
                utc = dt_timezone.utc
                current_time = current_time.replace(tzinfo=utc)
                tz = pytz_timezone(timezone)
                current_time = current_time.astimezone(tz)
        except Exception:
            # If timezone conversion fails, just use the time as-is
            pass
            
        current_time_only = current_time.time()
        
        # Simple case: start_time < end_time (same day window)
        if window_start <= window_end:
            return window_start <= current_time_only <= window_end
            
        # Complex case: start_time > end_time (overnight window)
        return current_time_only >= window_start or current_time_only <= window_end

class UserPreferencesResponse(BaseModel):
    """User preferences response schema."""
    id: UUID
    user_id: UUID
    theme: Theme
    language: Language
    timezone: str
    enabled_channels: List[NotificationChannel]
    notification_frequency: Dict[str, Dict[str, str]]  # Updated to match database format
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

class UserPreferencesCreate(BaseModel):
    """User preferences creation schema."""
    user_id: UUID
    theme: Theme = Theme.SYSTEM
    language: Language = Language.EN
    timezone: str = "UTC"
    enabled_channels: List[NotificationChannel] = Field(
        default=[NotificationChannel.IN_APP, NotificationChannel.EMAIL]
    )
    notification_frequency: Dict[NotificationType, NotificationFrequency] = Field(
        default_factory=lambda: {
            NotificationType.DEAL: NotificationFrequency.IMMEDIATE,
            NotificationType.GOAL: NotificationFrequency.IMMEDIATE,
            NotificationType.PRICE_ALERT: NotificationFrequency.IMMEDIATE,
            NotificationType.TOKEN: NotificationFrequency.DAILY,
            NotificationType.SECURITY: NotificationFrequency.IMMEDIATE,
            NotificationType.MARKET: NotificationFrequency.DAILY,
            NotificationType.SYSTEM: NotificationFrequency.IMMEDIATE
        }
    )
    time_windows: Dict[NotificationChannel, NotificationTimeWindow] = Field(
        default_factory=lambda: {
            NotificationChannel.IN_APP: NotificationTimeWindow(),
            NotificationChannel.EMAIL: NotificationTimeWindow()
        }
    )
    muted_until: Optional[time] = None
    do_not_disturb: bool = False
    email_digest: bool = True
    push_enabled: bool = True
    sms_enabled: bool = False
    telegram_enabled: bool = False
    discord_enabled: bool = False
    minimum_priority: str = "low"
    deal_alert_settings: Dict = Field(default_factory=dict)
    price_alert_settings: Dict = Field(default_factory=dict)
    email_preferences: Dict = Field(default_factory=dict)

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