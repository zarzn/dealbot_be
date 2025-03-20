"""Feature announcement notification template."""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from core.notifications.templates import NotificationTemplate
from core.models.notification import NotificationChannel, NotificationPriority, NotificationType


class FeatureAnnouncementTemplate(NotificationTemplate):
    """Template for feature announcement notifications."""
    
    template_id: str = "feature_announcement"
    notification_type: NotificationType = NotificationType.SYSTEM
    title: str = "New Feature Announcement" 
    message: str = "We've added a new feature to the platform!"
    default_channels: list = [
        NotificationChannel.EMAIL,
        NotificationChannel.PUSH,
        NotificationChannel.IN_APP
    ]
    priority: NotificationPriority = NotificationPriority.MEDIUM
    action_required: bool = False
    action_url: Optional[str] = None
    default_metadata: Dict[str, Any] = {"event": "feature_announcement"}
    
    # Additional fields specific to this template
    required_params: list = ["announcement_title", "announcement_content"]
    optional_params: list = ["action_url", "action_text"]
    
    async def generate_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the notification content.
        
        Args:
            params: Parameters for the notification
            
        Returns:
            Dict containing the notification content
        """
        title = params.get("announcement_title", self.title)
        content = params.get("announcement_content", self.message)
        
        # Create the body content
        body = f"{content}"
        
        # Add action information if available
        action_url = params.get("action_url")
        action_text = params.get("action_text", "Learn More")
        
        if action_url:
            action_info = {
                "url": action_url,
                "text": action_text
            }
        else:
            action_info = None
        
        # Create the email content with more formatting
        email_content = f"""
        <h2>{title}</h2>
        <p>{content}</p>
        """
        
        if action_url:
            email_content += f"""
            <p><a href="{action_url}" style="display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">{action_text}</a></p>
            """
        
        return {
            "title": title,
            "body": body,
            "email_subject": f"New Feature: {title}",
            "email_content": email_content,
            "action": action_info
        }
        
    async def get_priority(self, params: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> NotificationPriority:
        """Get the priority of this notification.
        
        Args:
            params: Parameters for the notification
            metadata: Additional metadata
            
        Returns:
            Notification priority
        """
        # Check if this is marked as an important announcement
        if metadata and metadata.get("is_important"):
            return NotificationPriority.HIGH
        
        return self.priority 