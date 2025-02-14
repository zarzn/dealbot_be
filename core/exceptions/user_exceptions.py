"""User-related exceptions."""

from typing import Optional, Dict, Any, List
from .base_exceptions import BaseError, ValidationError

class UserError(BaseError):
    """Base class for user-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class UserNotFoundError(UserError):
    """Raised when a user is not found."""
    
    def __init__(
        self,
        message: str = "User not found",
        user_id: Optional[str] = None,
        email: Optional[str] = None
    ):
        details = {}
        if user_id:
            details["user_id"] = user_id
        if email:
            details["email"] = email
            
        super().__init__(
            message=message,
            details=details
        )

class DuplicateUserError(UserError):
    """Raised when attempting to create a duplicate user."""
    
    def __init__(
        self,
        message: str = "User already exists",
        email: Optional[str] = None
    ):
        details = {}
        if email:
            details["email"] = email
            
        super().__init__(
            message=message,
            details=details
        )

class InvalidUserDataError(UserError):
    """Raised when user data is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid user data",
        errors: Optional[Dict[str, str]] = None
    ):
        super().__init__(
            message=message,
            details={"errors": errors or {}}
        )

class UserValidationError(ValidationError):
    """Raised when user validation fails."""
    
    def __init__(
        self,
        message: str = "User validation failed",
        errors: Optional[Dict[str, Any]] = None,
        field_prefix: str = "user"
    ):
        super().__init__(
            message=message,
            errors=errors,
            field_prefix=field_prefix
        )

__all__ = [
    'UserError',
    'UserNotFoundError',
    'DuplicateUserError',
    'InvalidUserDataError',
    'UserValidationError'
]
