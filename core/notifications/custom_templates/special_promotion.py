"""Special promotion notification template."""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from core.notifications.templates import NotificationTemplate
from core.models.notification import NotificationChannel, NotificationPriority, NotificationType


class SpecialPromotionTemplate(NotificationTemplate):
    """Template for special promotion notifications."""
    
    template_id: str = "special_promotion"
    notification_type: NotificationType = NotificationType.PRICE_ALERT
    title: str = "Special Promotion"
    message: str = "Check out this special promotion!"
    default_channels: list = [
        NotificationChannel.EMAIL,
        NotificationChannel.PUSH,
        NotificationChannel.IN_APP
    ]
    priority: NotificationPriority = NotificationPriority.MEDIUM
    action_required: bool = False
    action_url: Optional[str] = None
    default_metadata: Dict[str, Any] = {"event": "special_promotion"}
    
    required_params: list = ["promotion_title", "promotion_description"]
    optional_params: list = ["token_amount", "market_name", "discount_percentage", 
                       "promotion_start", "promotion_end"]
    
    async def generate_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the notification content.
        
        Args:
            params: Parameters for the notification
            
        Returns:
            Dict containing the notification content
        """
        # Get basic parameters
        title = params.get("promotion_title", self.title)
        description = params.get("promotion_description", self.message)
        
        # Determine promotion type based on parameters
        is_token_promotion = "token_amount" in params
        is_deal_promotion = "discount_percentage" in params
        
        # Customize the message based on promotion type
        if is_token_promotion:
            token_amount = params.get("token_amount")
            body = f"{description}. You've received {token_amount} tokens!"
            email_subject = f"You've received {token_amount} tokens: {title}"
        elif is_deal_promotion:
            discount = params.get("discount_percentage")
            market = params.get("market_name", "our marketplace")
            
            # Add timing information if available
            timing_info = ""
            if "promotion_start" in params and "promotion_end" in params:
                timing_info = f" from {params['promotion_start']} to {params['promotion_end']}"
                
            body = f"{description}. Get {discount}% off in {market}{timing_info}!"
            email_subject = f"{discount}% Off Special: {title}"
        else:
            # Generic promotion
            body = description
            email_subject = f"Special Promotion: {title}"
        
        # Create the email content with more formatting
        email_content = f"""
        <h2>{title}</h2>
        <p>{description}</p>
        """
        
        if is_token_promotion:
            token_amount = params.get("token_amount")
            email_content += f"""
            <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin: 15px 0; border-radius: 4px;">
                <h3 style="color: #28a745; margin-top: 0;">Token Reward</h3>
                <p>Congratulations! <strong>{token_amount} tokens</strong> have been added to your account.</p>
            </div>
            """
        elif is_deal_promotion:
            discount = params.get("discount_percentage")
            market = params.get("market_name", "our marketplace")
            
            email_content += f"""
            <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; margin: 15px 0; border-radius: 4px;">
                <h3 style="color: #dc3545; margin-top: 0;">Special Discount</h3>
                <p>Enjoy <strong>{discount}% off</strong> in {market}!</p>
            """
            
            if "promotion_start" in params and "promotion_end" in params:
                email_content += f"""
                <p><small>Promotion valid from {params['promotion_start']} to {params['promotion_end']}</small></p>
                """
                
            email_content += "</div>"
        
        # Add action information if available (from metadata or announcement direct link)
        action_info = None
        
        return {
            "title": title,
            "body": body,
            "email_subject": email_subject,
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
        # Token promotions are higher priority
        if "token_amount" in params:
            return NotificationPriority.HIGH
        
        # Flash deals (short duration) are higher priority
        if metadata and metadata.get("promotion_type") == "flash_deal":
            return NotificationPriority.HIGH
            
        # Check if this is marked as an important promotion
        if metadata and metadata.get("is_important"):
            return NotificationPriority.HIGH
        
        return self.priority 