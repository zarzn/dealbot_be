from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator

from core.models.user import UserResponse

class RegisterRequest(BaseModel):
    """Register request schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr

class NewPasswordRequest(BaseModel):
    """New password request schema."""
    password: str = Field(..., min_length=8)

class MagicLinkRequest(BaseModel):
    """Magic link request schema."""
    email: EmailStr

class SocialLoginRequest(BaseModel):
    """Social login request schema."""
    provider: str
    token: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None

class AuthResponse(BaseModel):
    """Authentication response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

    class Config:
        from_attributes = True 