"""User metadata model.

This module contains the model for storing user metadata, including feature flags,
preferences, and other settings.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from core.models.base import Base


class UserMetadata(Base):
    """Model for storing user metadata.
    
    This model is used to store various metadata related to users, such as
    feature flags, preferences, and other settings.
    """
    
    __tablename__ = "user_metadata"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationship to User model
    user = relationship("User", back_populates="user_metadata")
    
    def __repr__(self) -> str:
        return f"<UserMetadata(id={self.id}, user_id={self.user_id}, key={self.key})>" 