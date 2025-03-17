"""Auth token model module.

This module defines the AuthToken model and related Pydantic schemas for managing
authentication tokens in the AI Agentic Deals System.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index, update, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import text
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from core.exceptions import TokenError
import logging

from core.models.base import Base
from core.models.enums import TokenType, TokenStatus, TokenScope
# Remove circular import:
# from core.models.user import User
from core.config import settings

logger = logging.getLogger(__name__)

class TokenErrorType(str, enum.Enum):
    """Token error type enumeration."""
    INVALID = "invalid"
    EXPIRED = "expired"
    BLACKLISTED = "blacklisted"
    INVALID_TYPE = "invalid_type"
    MALFORMED = "malformed"
    MISSING = "missing"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    INVALID_FORMAT = "invalid_format"

class AuthToken(Base):
    """Auth token model."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index('ix_auth_tokens_user', 'user_id'),
        Index('ix_auth_tokens_token', 'token'),
        Index('ix_auth_tokens_status', 'status'),
        {'extend_existing': True}
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text('gen_random_uuid()')
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='active')
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default='full')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
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

    # Use a string for the User relationship to avoid circular imports
    user = relationship("User", back_populates="auth_tokens", foreign_keys=[user_id])

    def __repr__(self) -> str:
        """String representation of the auth token."""
        return f"<AuthToken {self.token_type} ({self.status})>"

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        user_id: UUID,
        token_type: TokenType,
        token: str,
        status: TokenStatus = TokenStatus.ACTIVE,
        scope: TokenScope = TokenScope.FULL,
        expires_at: Optional[datetime] = None,
        meta_data: Optional[dict] = None,
    ) -> "AuthToken":
        """Create a new auth token."""
        if not expires_at:
            expires_at = datetime.utcnow() + timedelta(days=30)

        auth_token = cls(
            user_id=user_id,
            token=token,
            token_type=token_type.value,
            status=status.value,
            scope=scope.value,
            expires_at=expires_at,
            meta_data=meta_data,
        )
        db.add(auth_token)
        await db.commit()
        await db.refresh(auth_token)
        return auth_token

    @classmethod
    async def revoke_all_user_tokens(
        cls, db: AsyncSession, user_id: UUID
    ) -> None:
        """Revoke all active tokens for a user."""
        stmt = (
            select(cls)
            .where(cls.user_id == user_id)
            .where(cls.status == TokenStatus.ACTIVE.value)
        )
        result = await db.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            token.status = TokenStatus.REVOKED.value
            token.updated_at = datetime.utcnow()

        await db.commit()

    @classmethod
    async def get_by_token(
        cls, db: AsyncSession, token: str
    ) -> Optional["AuthToken"]:
        """Get token by value."""
        stmt = select(cls).where(cls.token == token)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid."""
        return (
            self.status == TokenStatus.ACTIVE.value
            and not self.is_expired
        )

class AuthTokenCreate(BaseModel):
    """Model for creating a new auth token."""
    user_id: UUID
    token_type: TokenType
    token: str
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