"""Authentication models module.

This module defines the authentication-related models and schemas for the AI Agentic Deals System.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import text

from core.models.base import Base

class TokenType(str, Enum):
    """Token type enumeration."""
    BEARER = "bearer"
    REFRESH = "refresh"

class TokenStatus(str, Enum):
    """Token status enumeration."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"

class TokenScope(str, Enum):
    """Token scope enumeration."""
    FULL = "full"
    READ = "read"
    WRITE = "write"

class AuthToken(Base):
    """Authentication token database model."""
    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index('ix_auth_tokens_user', 'user_id'),
        Index('ix_auth_tokens_token', 'token'),
        Index('ix_auth_tokens_status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    token_type: Mapped[TokenType] = mapped_column(SQLEnum(TokenType), nullable=False)
    status: Mapped[TokenStatus] = mapped_column(SQLEnum(TokenStatus), default=TokenStatus.ACTIVE)
    scope: Mapped[TokenScope] = mapped_column(SQLEnum(TokenScope), default=TokenScope.FULL)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # Relationships
    user = relationship("User", back_populates="auth_tokens")

    def __repr__(self) -> str:
        """String representation of the token."""
        return f"<AuthToken {self.token_type} ({self.status})>"

    async def revoke(self) -> None:
        """Revoke the token."""
        self.status = TokenStatus.REVOKED

    async def is_valid(self) -> bool:
        """Check if token is valid."""
        return (
            self.status == TokenStatus.ACTIVE and
            datetime.utcnow() < self.expires_at
        )

class Token(BaseModel):
    """Token schema."""
    access_token: str
    token_type: TokenType = TokenType.BEARER

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
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

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
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

class UserProfile(Base):
    """User profile database model."""
    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    user = relationship("AuthUser", back_populates="profile")

    def __repr__(self) -> str:
        """String representation of the profile."""
        return f"<UserProfile(user_id={self.user_id})>"

class AuthUser(Base):
    """Authentication user database model."""
    __tablename__ = "auth_users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
        onupdate=text('CURRENT_TIMESTAMP')
    )

    # Relationships
    tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<AuthUser(email={self.email}, is_active={self.is_active})>" 