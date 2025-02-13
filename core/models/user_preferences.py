"""User preferences models."""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID
from pydantic import BaseModel

from sqlalchemy import Column, ForeignKey, String, JSON, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from core.database import Base

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

class UserPreferences(Base):
    """User preferences model."""

    __tablename__ = "user_preferences"

    id = Column(PGUUID, primary_key=True)
    user_id = Column(PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    theme = Column(String, default=Theme.SYSTEM)
    language = Column(String, default=Language.EN)
    timezone = Column(String, default="UTC")
    notification_settings = Column(JSON, default={})
    deal_alert_settings = Column(JSON, default={})
    price_alert_settings = Column(JSON, default={})
    email_preferences = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="preferences")

class UserPreferencesResponse(BaseModel):
    """User preferences response schema."""
    id: UUID
    user_id: UUID
    theme: Theme
    language: Language
    timezone: str
    notification_settings: Dict
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
    notification_settings: Optional[Dict] = None
    deal_alert_settings: Optional[Dict] = None
    price_alert_settings: Optional[Dict] = None
    email_preferences: Optional[Dict] = None 