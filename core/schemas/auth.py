"""Authentication schemas module.

This module defines the request and response models for authentication endpoints.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, validator, constr
import re
from uuid import UUID

from core.models.enums import UserStatus
from core.schemas.user import UserResponse

class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    """Register request schema."""
    email: EmailStr
    password: constr(min_length=8)
    name: str

    @validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password complexity."""
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one number, and one special character"
            )
        return v

class RegisterResponse(TokenResponse):
    """Register response schema."""
    user: UserResponse

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str

class LoginResponse(TokenResponse):
    """Login response schema."""
    user: UserResponse

class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str

class RequestPasswordResetRequest(BaseModel):
    """Request password reset request schema."""
    email: EmailStr

class VerifyEmailRequest(BaseModel):
    """Email verification request schema."""
    token: str

class NewPasswordRequest(BaseModel):
    """New password request schema."""
    password: constr(min_length=8)

    @validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

class NewPasswordResponse(BaseModel):
    """New password response schema."""
    msg: str

class MagicLinkRequest(BaseModel):
    """Magic link request schema."""
    email: EmailStr

class SocialLoginRequest(BaseModel):
    """Social login request schema."""
    provider: str
    token: str

class AuthResponse(BaseModel):
    """Authentication response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

    class Config:
        from_attributes = True

class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: str
    exp: Optional[datetime] = None

class TokenData(BaseModel):
    """Token data schema."""
    user_id: str
    expires: datetime

class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PasswordResetResponse(BaseModel):
    """Password reset response schema."""
    message: str

class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    token: str
    password: constr(min_length=8)

    @validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password complexity."""
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one number, and one special character"
            )
        return v 