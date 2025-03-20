"""Notifications Package.

This package provides a complete templated notification system.
"""

# Import from our new registry instead of directly from templates
from core.notifications.template_registry import (
    TEMPLATES as NOTIFICATION_TEMPLATES,
    get_template
)

# Import necessary components
from core.notifications.factory import NotificationFactory
from core.notifications.service import TemplatedNotificationService

# Create a function to get the notification service
async def get_notification_service(db_session):
    """Get the templated notification service."""
    return TemplatedNotificationService(db_session) 