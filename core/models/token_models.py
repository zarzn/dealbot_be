"""Token models module."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field

from core.models.enums import TokenTransactionType, TokenTransactionStatus
from core.models.token_transaction import TokenTransaction

__all__ = ['Token', 'TokenData', 'TokenTransaction']

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

    class Config:
        from_attributes = True

class TokenData(BaseModel):
    """Token data model for decoded JWT payload."""
    sub: str  # User ID
    exp: Optional[int] = None  # Expiration timestamp
    type: Optional[str] = None  # Token type (access, refresh, etc.)
    scope: Optional[str] = None  # Token scope
    refresh: Optional[bool] = None  # Whether this is a refresh token
    jti: Optional[str] = None  # JWT ID for blacklisting

    class Config:
        from_attributes = True 