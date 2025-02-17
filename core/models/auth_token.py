"""Auth token model module.

This module defines the AuthToken model and related Pydantic schemas for managing
authentication tokens in the AI Agentic Deals System.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import text
from pydantic import BaseModel, Field

from core.models.base import Base

class TokenType(str, enum.Enum):
    """Token type enumeration."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    VERIFY = "verify"

class TokenStatus(str, enum.Enum):
    """Token status types."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"

class TokenScope(str, enum.Enum):
    """Token scope types."""
    FULL = "full"
    READ = "read"
    WRITE = "write"

class AuthToken(Base):
    """Auth token database model."""
    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index('ix_auth_tokens_user', 'user_id'),
        Index('ix_auth_tokens_token', 'token'),
        Index('ix_auth_tokens_status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    token_type: Mapped[TokenType] = mapped_column(SQLEnum(TokenType), nullable=False)
    status: Mapped[TokenStatus] = mapped_column(SQLEnum(TokenStatus), default=TokenStatus.ACTIVE)
    scope: Mapped[TokenScope] = mapped_column(SQLEnum(TokenScope), default=TokenScope.FULL)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))

    # Relationships
    user = relationship("User", back_populates="auth_tokens")

    def __repr__(self) -> str:
        """String representation of the auth token."""
        return f"<AuthToken {self.token_type} ({self.status})>"

class AuthTokenCreate(BaseModel):
    """Model for creating a new auth token."""
    user_id: UUID
    token_type: TokenType
    scope: TokenScope = TokenScope.FULL
    expires_at: datetime
    meta_data: Optional[Dict[str, Any]] = None

class AuthTokenUpdate(BaseModel):
    """Model for updating an auth token."""
    status: Optional[TokenStatus] = None
    scope: Optional[TokenScope] = None
    expires_at: Optional[datetime] = None
    meta_data: Optional[Dict[str, Any]] = None

class AuthTokenResponse(BaseModel):
    """Response model for auth token."""
    id: UUID
    user_id: UUID
    token_type: TokenType
    status: TokenStatus
    scope: TokenScope
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    meta_data: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic model configuration."""
        from_attributes = True 