"""Notification Factory Module.

This module provides a factory for creating notifications from templates,
ensuring consistent formatting and standardization across the application.
"""

from typing import Dict, Any, List, Optional, Union
from uuid import UUID
from datetime import datetime
import logging
from string import Formatter

from core.models.notification import (
    NotificationType,
    NotificationChannel,
    NotificationPriority
)
from core.notifications.templates import NotificationTemplate
from core.notifications.template_registry import get_template

logger = logging.getLogger(__name__)

class NotificationFactory:
    """Factory for creating notifications from templates."""
    
    @classmethod
    def create_notification(
        cls,
        template_id: str,
        user_id: UUID,
        template_params: Optional[Dict[str, Any]] = None,
        override_channels: Optional[List[NotificationChannel]] = None,
        override_priority: Optional[NotificationPriority] = None,
        metadata: Optional[Dict[str, Any]] = None,
        goal_id: Optional[UUID] = None,
        deal_id: Optional[UUID] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a notification using a template.
        
        Args:
            template_id: ID of the template to use
            user_id: ID of the user to notify
            template_params: Parameters to format into the template message
            override_channels: Override default channels from template
            override_priority: Override default priority from template
            metadata: Additional metadata to merge with template defaults
            goal_id: Optional goal ID related to the notification
            deal_id: Optional deal ID related to the notification
            action_url: Optional override for action URL
            
        Returns:
            Dict containing all notification parameters ready to be passed to 
            the notification service create_notification method
        """
        # Get the template
        template = cls._get_template(template_id)
        if not template:
            logger.error(f"Notification template not found: {template_id}")
            # Fallback to a generic notification
            return {
                "user_id": user_id,
                "title": "System Notification",
                "message": "An important system notification was generated.",
                "notification_type": NotificationType.SYSTEM,
                "channels": [NotificationChannel.IN_APP],
                "priority": NotificationPriority.MEDIUM,
                "notification_metadata": {"event": "system_notification", "template_error": True}
            }
        
        # Format the message and title with template params
        params = template_params or {}
        message = cls._format_template(template.message, params)
        title = cls._format_template(template.title, params)
        
        # Merge metadata
        notification_metadata = dict(template.default_metadata)
        if metadata:
            notification_metadata.update(metadata)
        
        # Make sure timestamp is in metadata
        if "timestamp" not in notification_metadata:
            notification_metadata["timestamp"] = datetime.utcnow().isoformat()
        
        # Use override values or template defaults
        channels = override_channels or template.default_channels
        priority = override_priority or template.priority
        
        # Process action URL with parameters if needed
        final_action_url = action_url or template.action_url
        if final_action_url:
            final_action_url = cls._format_template(final_action_url, params)
        
        # Return notification parameters dictionary
        return {
            "user_id": user_id,
            "title": title,
            "message": message,
            "notification_type": template.notification_type,
            "channels": channels,
            "priority": priority,
            "notification_metadata": notification_metadata,
            "goal_id": goal_id,
            "deal_id": deal_id,
            "action_url": final_action_url
        }
    
    @staticmethod
    def _get_template(template_id: str) -> Optional[NotificationTemplate]:
        """Get a notification template by ID."""
        return get_template(template_id)
    
    @staticmethod
    def _format_template(template_str: str, params: Dict[str, Any]) -> str:
        """Format a template string with parameters, handling missing values gracefully."""
        if not template_str:
            return ""
            
        # Extract all keys required by the template
        required_keys = [
            key for _, key, _, _ in Formatter().parse(template_str)
            if key is not None
        ]
        
        # Check if all required keys are provided
        for key in required_keys:
            if key not in params:
                logger.warning(f"Missing template parameter: {key}")
                # Replace missing parameters with placeholder
                params[key] = f"[{key}]"
        
        try:
            return template_str.format(**params)
        except KeyError as e:
            logger.error(f"Missing required template parameter: {e}")
            return template_str  # Return the unformatted template as fallback
        except Exception as e:
            logger.error(f"Error formatting template: {e}")
            return template_str  # Return the unformatted template as fallback 