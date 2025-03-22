"""Share-related exceptions.

This module defines exceptions for sharing-related operations.
"""

from core.exceptions import BaseError


class ShareException(BaseError):
    """Base exception for sharing operations."""
    def __init__(self, message: str = "Share operation failed", error_code: str = "share_error", details: dict = None):
        super().__init__(message=message, details=details)
        self.error_code = error_code


class ShareContentNotFoundException(ShareException):
    """Exception raised when shared content is not found."""
    def __init__(self, share_id: str = None, message: str = None):
        msg = message or f"Shared content {'with ID ' + share_id if share_id else ''} not found"
        super().__init__(message=msg)
        self.error_code = "content_not_found"


class ShareExpiredException(ShareException):
    """Exception raised when a share link has expired."""
    def __init__(self, share_id: str = None):
        msg = f"Share link {'with ID ' + share_id if share_id else ''} has expired"
        super().__init__(message=msg)
        self.error_code = "share_expired"


class ShareDeactivatedException(ShareException):
    """Exception raised when a share link has been deactivated."""
    def __init__(self, share_id: str = None):
        msg = f"Share link {'with ID ' + share_id if share_id else ''} has been deactivated"
        super().__init__(message=msg)
        self.error_code = "share_deactivated"


class ShareAuthorizationException(ShareException):
    """Exception raised when a user is not authorized to access or manage a share."""
    def __init__(self, message: str = "You are not authorized to access this content"):
        super().__init__(message=message)
        self.error_code = "share_unauthorized"


class InvalidShareContentTypeException(ShareException):
    """Exception raised when an invalid content type is specified for sharing."""
    def __init__(self, content_type: str = None):
        msg = f"Invalid content type {'(' + content_type + ')' if content_type else ''} for sharing"
        super().__init__(message=msg)
        self.error_code = "invalid_content_type"


class ShareValidationException(ShareException):
    """Exception raised when share content validation fails."""
    def __init__(self, message: str = "Share content validation failed"):
        super().__init__(message=message)
        self.error_code = "validation_error" 