"""Notification-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base import BaseError, ValidationError

class NotificationError(BaseError):
    """Base class for notification-related errors."""
    
    def __init__(
        self,
        message: str = "Notification operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="notification_error",
            details=details
        )

class NotificationNotFoundError(NotificationError):
    """Raised when a notification cannot be found."""
    
    def __init__(
        self,
        notification_id: str,
        message: str = "Notification not found"
    ):
        super().__init__(
            message=message,
            details={"notification_id": notification_id}
        )

class NotificationDeliveryError(NotificationError):
    """Raised when a notification fails to be delivered."""
    
    def __init__(
        self,
        notification_id: str,
        delivery_method: str,
        error_details: Optional[Dict[str, Any]] = None,
        message: str = "Notification delivery failed"
    ):
        super().__init__(
            message=message,
            details={
                "notification_id": notification_id,
                "delivery_method": delivery_method,
                "error_details": error_details or {}
            }
        )

class NotificationRateLimitError(NotificationError):
    """Raised when notification rate limit is exceeded."""
    
    def __init__(
        self,
        user_id: str,
        current_count: int,
        limit: int,
        time_window: str,
        message: str = "Notification rate limit exceeded"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "current_count": current_count,
                "limit": limit,
                "time_window": time_window
            }
        )

class InvalidNotificationTemplateError(NotificationError):
    """Raised when a notification template is invalid."""
    
    def __init__(
        self,
        template_id: str,
        validation_errors: List[str],
        message: str = "Invalid notification template"
    ):
        super().__init__(
            message=message,
            details={
                "template_id": template_id,
                "validation_errors": validation_errors
            }
        )

__all__ = [
    'NotificationError',
    'NotificationNotFoundError',
    'NotificationDeliveryError',
    'NotificationRateLimitError',
    'InvalidNotificationTemplateError'
] 