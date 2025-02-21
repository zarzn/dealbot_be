"""Authentication models module.

This module defines the authentication-related models and schemas for the AI Agentic Deals System.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Index, Float, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import text, func

from core.models.base import Base
from .auth_token import TokenType, TokenStatus, TokenScope, AuthToken

class Token(BaseModel):
    """Token schema."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")

class TokenData(BaseModel):
    """Token data schema."""
    email: Optional[str] = None
    user_id: Optional[UUID] = None

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        """Validate that passwords match."""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    sol_address: Optional[str] = None

class UserInDB(UserBase):
    """Schema for user in database."""
    id: UUID
    hashed_password: str
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    sol_address: Optional[str] = None
    token_balance: float = 0.0

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

class UserProfile(Base):
    """User profile database model."""
    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        """String representation of the profile."""
        return f"<UserProfile(user_id={self.user_id})>"

class User(Base):
    """User model."""
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sol_address: Mapped[Optional[str]] = mapped_column(String(44), unique=True, nullable=True)
    token_balance: Mapped[float] = mapped_column(Numeric(precision=18, scale=8), default=0.0, nullable=False)

    # Relationships
    tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    token_transactions = relationship("TokenTransaction", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User {self.email}>"

    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "sol_address": self.sol_address,
            "token_balance": float(self.token_balance) if self.token_balance is not None else 0.0
        } 