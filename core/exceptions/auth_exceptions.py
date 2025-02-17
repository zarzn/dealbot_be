"""Authentication-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base_exceptions import BaseError, ValidationError

class AuthError(BaseError):
    """Base class for authentication-related errors."""
    
    def __init__(
        self,
        message: str = "Authentication operation failed",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code or "auth_error",
            details=details
        )

class AuthenticationError(AuthError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if reason:
            error_details["reason"] = reason
        super().__init__(
            message=message,
            details=error_details
        )

class AuthorizationError(AuthError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if resource:
            error_details["resource"] = resource
        if action:
            error_details["action"] = action
        super().__init__(
            message=message,
            details=error_details
        )

class InvalidCredentialsError(AuthError):
    """Raised when credentials are invalid."""
    
    def __init__(
        self,
        message: str = "Invalid credentials",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code or "invalid_credentials",
            details=details or {}
        )

class TokenError(AuthError):
    """Raised when there's an issue with authentication tokens."""
    
    def __init__(
        self,
        token_type: str,
        error_type: str,
        message: str = "Token error",
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "token_type": token_type,
            "error_type": error_type
        })
        super().__init__(
            message=message,
            details=error_details
        )

class SessionExpiredError(AuthError):
    """Raised when a user session has expired."""
    
    def __init__(
        self,
        session_id: str,
        expiry_time: str,
        message: str = "Session expired"
    ):
        super().__init__(
            message=message,
            details={
                "session_id": session_id,
                "expiry_time": expiry_time
            }
        )

class PermissionDeniedError(AuthError):
    """Raised when user lacks required permissions."""
    
    def __init__(
        self,
        user_id: str,
        required_permissions: List[str],
        current_permissions: List[str],
        message: str = "Permission denied"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "required_permissions": required_permissions,
                "current_permissions": current_permissions
            }
        )

class TwoFactorRequiredError(AuthError):
    """Raised when 2FA is required but not provided."""
    
    def __init__(
        self,
        user_id: str,
        message: str = "Two-factor authentication required"
    ):
        super().__init__(
            message=message,
            details={"user_id": user_id}
        )

class InvalidTwoFactorCodeError(AuthError):
    """Raised when 2FA code is invalid."""
    
    def __init__(
        self,
        user_id: str,
        attempts_remaining: int,
        message: str = "Invalid two-factor code"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "attempts_remaining": attempts_remaining
            }
        )

class AccountLockedError(AuthError):
    """Raised when an account is locked due to too many failed login attempts."""
    
    def __init__(
        self,
        user_id: str,
        locked_until: str,
        attempts_made: int,
        max_attempts: int,
        message: str = "Account locked due to too many failed login attempts"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "locked_until": locked_until,
                "attempts_made": attempts_made,
                "max_attempts": max_attempts
            }
        )

class TokenRefreshError(AuthError):
    """Raised when token refresh fails."""
    
    def __init__(
        self,
        message: str = "Token refresh failed",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if reason:
            error_details["reason"] = reason
        super().__init__(
            message=message,
            details=error_details
        )

class EmailNotVerifiedError(AuthError):
    """Raised when a user attempts to perform an action that requires email verification."""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        message: str = "Email verification required"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "email": email,
                "verification_required": True
            }
        )

__all__ = [
    'AuthError',
    'AuthenticationError',
    'AuthorizationError',
    'InvalidCredentialsError',
    'TokenError',
    'SessionExpiredError',
    'PermissionDeniedError',
    'TwoFactorRequiredError',
    'InvalidTwoFactorCodeError',
    'TokenRefreshError',
    'AccountLockedError',
    'EmailNotVerifiedError'
] 