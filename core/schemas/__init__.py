"""Schemas package.

This package contains all the Pydantic models used for request/response validation.
"""

from .auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    NewPasswordRequest,
    NewPasswordResponse,
    TokenResponse,
    TokenRequest,
    RefreshTokenRequest,
    AccessTokenVerifyRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    RequestEmailVerificationRequest,
    VerifyEmailRequest,
    MagicLinkRequest,
)

from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
)

from .common import (
    ResponseStatus,
    StatusResponse,
    ErrorResponse,
    HealthResponse,
)

from .contact import (
    ContactFormRequest,
    ContactFormResponse,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "PasswordResetRequest",
    "PasswordResetResponse",
    "NewPasswordRequest",
    "NewPasswordResponse",
    "TokenResponse",
    "TokenRequest",
    "RefreshTokenRequest",
    "AccessTokenVerifyRequest",
    "RequestPasswordResetRequest",
    "ResetPasswordRequest",
    "RequestEmailVerificationRequest",
    "VerifyEmailRequest",
    "MagicLinkRequest",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    "ResponseStatus",
    "StatusResponse",
    "ErrorResponse",
    "HealthResponse",
    "ContactFormRequest",
    "ContactFormResponse",
] 