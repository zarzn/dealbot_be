"""Notification-related exceptions."""

from typing import Dict, Any, Optional
from .base_exceptions import BaseError, ValidationError

class NotificationError(BaseError):
    """Base class for notification-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class NotificationDeliveryError(NotificationError):
    """Raised when notification delivery fails."""
    
    def __init__(
        self,
        channel: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "channel": channel,
            "reason": reason
        })
        super().__init__(
            message=f"Failed to deliver notification via {channel}: {reason}",
            details=error_details
        )

class NotificationNotFoundError(NotificationError):
    """Raised when a notification is not found."""
    
    def __init__(
        self,
        notification_id: str,
        message: str = "Notification not found"
    ):
        super().__init__(
            message=message,
            details={"notification_id": notification_id}
        )

class NotificationRateLimitError(NotificationError):
    """Raised when notification rate limit is exceeded."""
    
    def __init__(
        self,
        channel: str,
        limit: int,
        window: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "channel": channel,
            "limit": limit,
            "window": window
        })
        super().__init__(
            message=f"Rate limit exceeded for {channel}: {limit} per {window}",
            details=error_details
        )

class InvalidNotificationTemplateError(NotificationError):
    """Raised when a notification template is invalid."""
    
    def __init__(
        self,
        template_id: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "template_id": template_id,
            "reason": reason
        })
        super().__init__(
            message=f"Invalid notification template {template_id}: {reason}",
            details=error_details
        )

class NotificationConfigurationError(NotificationError):
    """Raised when notification configuration is invalid."""
    
    def __init__(
        self,
        channel: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "channel": channel,
            "reason": reason
        })
        super().__init__(
            message=f"Invalid configuration for {channel}: {reason}",
            details=error_details
        )

class NotificationChannelError(NotificationError):
    """Raised when there's an error with a notification channel."""
    
    def __init__(
        self,
        channel: str,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "channel": channel,
            "operation": operation,
            "reason": reason
        })
        super().__init__(
            message=f"Channel {channel} error during {operation}: {reason}",
            details=error_details
        )

__all__ = [
    'NotificationError',
    'NotificationDeliveryError',
    'NotificationNotFoundError',
    'NotificationRateLimitError',
    'InvalidNotificationTemplateError',
    'NotificationConfigurationError',
    'NotificationChannelError'
] 