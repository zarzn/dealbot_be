"""Notification Templates Module.

This module defines all notification templates used throughout the application.
It serves as a single source of truth for notification content and configuration.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel

from core.models.notification import (
    NotificationType, 
    NotificationChannel, 
    NotificationPriority
)

# We'll move custom template integration to another file to avoid circular imports

class NotificationTemplate(BaseModel):
    """Base model for notification templates."""
    
    # Unique identifier for the notification template
    template_id: str
    
    # Category of the notification
    notification_type: NotificationType
    
    # Default notification title
    title: str
    
    # Default notification message template
    message: str
    
    # Default channels to deliver this notification
    default_channels: List[NotificationChannel]
    
    # Default priority for this notification
    priority: NotificationPriority
    
    # Whether this notification requires user action
    action_required: bool = False
    
    # Default URL to include in the notification, if any
    action_url: Optional[str] = None
    
    # Default metadata to include
    default_metadata: Dict[str, Any] = {}


# System Notifications
REGISTRATION_CONFIRMATION = NotificationTemplate(
    template_id="sys_registration_confirmation",
    notification_type=NotificationType.SYSTEM,
    title="Welcome to AI Agentic Deals",
    message="Thank you for registering! Your account has been successfully created.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    default_metadata={"event": "user_registration"},
)

SYSTEM_MAINTENANCE = NotificationTemplate(
    template_id="sys_maintenance",
    notification_type=NotificationType.SYSTEM,
    title="Scheduled Maintenance",
    message="Our system will be undergoing maintenance on {start_date} from {start_time} to {end_time}. Some services may be unavailable during this time.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    default_metadata={"event": "system_maintenance"},
)

FEATURE_ANNOUNCEMENT = NotificationTemplate(
    template_id="sys_feature_announcement",
    notification_type=NotificationType.SYSTEM,
    title="New Feature Available",
    message="We've just launched {feature_name}! {feature_description}",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    default_metadata={"event": "feature_announcement"},
)

# Remove references to custom templates that are causing circular imports
# FEATURE_ANNOUNCEMENT_CUSTOM = FeatureAnnouncementTemplate()
# SPECIAL_PROMOTION_CUSTOM = SpecialPromotionTemplate()

API_ERROR = NotificationTemplate(
    template_id="sys_api_error",
    notification_type=NotificationType.SYSTEM,
    title="System Error",
    message="We encountered an error processing your request. Our team has been notified.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.HIGH,
    action_required=False,
    default_metadata={"event": "api_error"},
)

# Security Notifications
PASSWORD_CHANGED = NotificationTemplate(
    template_id="sec_password_changed",
    notification_type=NotificationType.SECURITY,
    title="Password Changed",
    message="Your password has been successfully changed. If you did not make this change, please contact support immediately.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.CRITICAL,
    action_required=False,
    default_metadata={"event": "password_change"},
)

PASSWORD_RESET = NotificationTemplate(
    template_id="sec_password_reset",
    notification_type=NotificationType.SECURITY,
    title="Password Reset Complete",
    message="Your password has been successfully reset. If you did not request this change, please contact support immediately.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.CRITICAL,
    action_required=False,
    default_metadata={"event": "password_reset"},
)

NEW_DEVICE_LOGIN = NotificationTemplate(
    template_id="sec_new_device_login",
    notification_type=NotificationType.SECURITY,
    title="Login from New Device",
    message="We detected a new login to your account from {device_type} in {location}. If this wasn't you, please secure your account immediately.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.CRITICAL,
    action_required=True,
    action_url="/account/security",
    default_metadata={"event": "new_device_login"},
)

SECURITY_SETTINGS_UPDATED = NotificationTemplate(
    template_id="sec_settings_updated",
    notification_type=NotificationType.SECURITY,
    title="Security Settings Updated",
    message="Your security settings have been updated. If you did not make these changes, please contact support immediately.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    default_metadata={"event": "security_settings_update"},
)

SUSPICIOUS_ACTIVITY = NotificationTemplate(
    template_id="sec_suspicious_activity",
    notification_type=NotificationType.SECURITY,
    title="Suspicious Account Activity",
    message="We've detected suspicious activity on your account. Please review recent activity and secure your account if necessary.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.CRITICAL,
    action_required=True,
    action_url="/account/security/activity",
    default_metadata={"event": "suspicious_activity"},
)

# Deal Notifications
NEW_DEAL_CREATED = NotificationTemplate(
    template_id="deal_new",
    notification_type=NotificationType.DEAL,
    title="New Deal Found",
    message="We found a new deal matching your preferences: {deal_title}",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/deals/{deal_id}",
    default_metadata={"event": "new_deal"},
)

DEAL_PRICE_CHANGE = NotificationTemplate(
    template_id="deal_price_change",
    notification_type=NotificationType.DEAL,
    title="Price Changed on Watched Deal",
    message="The price of {deal_title} has changed from {old_price} to {new_price}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/deals/{deal_id}",
    default_metadata={"event": "deal_price_change"},
)

DEAL_STATUS_UPDATE = NotificationTemplate(
    template_id="deal_status_update",
    notification_type=NotificationType.DEAL,
    title="Deal Status Update",
    message="The status of {deal_title} has changed to {status}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/deals/{deal_id}",
    default_metadata={"event": "deal_status_update"},
)

DEAL_RECOMMENDATION = NotificationTemplate(
    template_id="deal_recommendation",
    notification_type=NotificationType.DEAL,
    title="Recommended Deal",
    message="Based on your interests, we think you'll like this deal: {deal_title}",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.LOW,
    action_required=False,
    action_url="/deals/{deal_id}",
    default_metadata={"event": "deal_recommendation"},
)

# Goal Notifications
GOAL_CREATED = NotificationTemplate(
    template_id="goal_created",
    notification_type=NotificationType.GOAL,
    title="Goal Created",
    message="Your goal '{goal_title}' has been created successfully.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/goals/{goal_id}",
    default_metadata={"event": "goal_created"},
)

GOAL_PROGRESS_UPDATE = NotificationTemplate(
    template_id="goal_progress_update",
    notification_type=NotificationType.GOAL,
    title="Goal Progress Update",
    message="You've reached {progress}% of your goal '{goal_title}'.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/goals/{goal_id}",
    default_metadata={"event": "goal_progress_update"},
)

GOAL_COMPLETED = NotificationTemplate(
    template_id="goal_completed",
    notification_type=NotificationType.GOAL,
    title="Goal Completed!",
    message="Congratulations! You've completed your goal '{goal_title}'.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/goals/{goal_id}",
    default_metadata={"event": "goal_completed"},
)

GOAL_DEADLINE_APPROACHING = NotificationTemplate(
    template_id="goal_deadline_approaching",
    notification_type=NotificationType.GOAL,
    title="Goal Deadline Approaching",
    message="Your goal '{goal_title}' deadline is approaching. {days_left} days remaining.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/goals/{goal_id}",
    default_metadata={"event": "goal_deadline_approaching"},
)

# Price Alert Notifications
PRICE_DROP_ALERT = NotificationTemplate(
    template_id="price_drop_alert",
    notification_type=NotificationType.PRICE_ALERT,
    title="Price Drop Alert",
    message="The price of {item_name} has dropped below your target price of {target_price}.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/price-alerts/{alert_id}",
    default_metadata={"event": "price_drop"},
)

PRICE_INCREASE_ALERT = NotificationTemplate(
    template_id="price_increase_alert",
    notification_type=NotificationType.PRICE_ALERT,
    title="Price Increase Alert",
    message="The price of {item_name} has increased above {threshold_price}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/price-alerts/{alert_id}",
    default_metadata={"event": "price_increase"},
)

SPECIAL_PROMOTION = NotificationTemplate(
    template_id="special_promotion",
    notification_type=NotificationType.PRICE_ALERT,
    title="Special Promotion",
    message="Limited time offer: {promotion_description}",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/promotions/{promotion_id}",
    default_metadata={"event": "special_promotion"},
)

FLASH_DEAL = NotificationTemplate(
    template_id="flash_deal",
    notification_type=NotificationType.PRICE_ALERT,
    title="⚡ Flash Deal",
    message="Act fast! {deal_description} - Limited quantities available.",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/deals/{deal_id}",
    default_metadata={"event": "flash_deal"},
)

# Token Notifications
TOKEN_BALANCE_CHANGE = NotificationTemplate(
    template_id="token_balance_change",
    notification_type=NotificationType.TOKEN,
    title="Token Balance Update",
    message="Your token balance has changed by {amount}. New balance: {new_balance}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/account/tokens",
    default_metadata={"event": "token_balance_change"},
)

TOKEN_REWARD = NotificationTemplate(
    template_id="token_reward",
    notification_type=NotificationType.TOKEN,
    title="Token Reward",
    message="You've earned {amount} tokens for {reason}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/account/tokens",
    default_metadata={"event": "token_reward"},
)

TOKEN_EXPIRATION_WARNING = NotificationTemplate(
    template_id="token_expiration_warning",
    notification_type=NotificationType.TOKEN,
    title="Tokens Expiring Soon",
    message="{amount} tokens will expire in {days_left} days. Use them before they expire!",
    default_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    priority=NotificationPriority.HIGH,
    action_required=True,
    action_url="/account/tokens",
    default_metadata={"event": "token_expiration_warning"},
)

TOKEN_USAGE_OPPORTUNITY = NotificationTemplate(
    template_id="token_usage_opportunity",
    notification_type=NotificationType.TOKEN,
    title="Use Your Tokens",
    message="You have {amount} unused tokens. Here's a suggestion: {suggestion}",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.LOW,
    action_required=False,
    action_url="/account/tokens",
    default_metadata={"event": "token_usage_opportunity"},
)

# Market Notifications
NEW_MARKET_ADDED = NotificationTemplate(
    template_id="market_new",
    notification_type=NotificationType.MARKET,
    title="New Market Added",
    message="We've added a new market: {market_name}. Explore new opportunities now!",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/markets/{market_id}",
    default_metadata={"event": "new_market"},
)

MARKET_STATUS_CHANGE = NotificationTemplate(
    template_id="market_status_change",
    notification_type=NotificationType.MARKET,
    title="Market Status Change",
    message="The status of {market_name} has changed to {status}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.HIGH,
    action_required=False,
    action_url="/markets/{market_id}",
    default_metadata={"event": "market_status_change"},
)

MARKET_TREND = NotificationTemplate(
    template_id="market_trend",
    notification_type=NotificationType.MARKET,
    title="Market Trend Alert",
    message="{trend_description} in {market_name}.",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.LOW,
    action_required=False,
    action_url="/markets/{market_id}/trends",
    default_metadata={"event": "market_trend"},
)

MARKET_OPPORTUNITY = NotificationTemplate(
    template_id="market_opportunity",
    notification_type=NotificationType.MARKET,
    title="Market Opportunity",
    message="Potential opportunity in {market_name}: {opportunity_description}",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    action_url="/markets/{market_id}/opportunities",
    default_metadata={"event": "market_opportunity"},
)

# Mapping of template_ids to templates for easy lookup
NOTIFICATION_TEMPLATES = {
    # System notifications
    "sys_registration_confirmation": REGISTRATION_CONFIRMATION,
    "sys_maintenance": SYSTEM_MAINTENANCE,
    "sys_feature_announcement": FEATURE_ANNOUNCEMENT,
    # Remove references to custom templates
    # "feature_announcement": FEATURE_ANNOUNCEMENT_CUSTOM,
    "sys_api_error": API_ERROR,
    
    # Security notifications
    "sec_password_changed": PASSWORD_CHANGED,
    "sec_password_reset": PASSWORD_RESET,
    "sec_new_device_login": NEW_DEVICE_LOGIN,
    "sec_settings_updated": SECURITY_SETTINGS_UPDATED,
    "sec_suspicious_activity": SUSPICIOUS_ACTIVITY,
    
    # Deal notifications
    "deal_new": NEW_DEAL_CREATED,
    "deal_price_change": DEAL_PRICE_CHANGE,
    "deal_status_update": DEAL_STATUS_UPDATE,
    "deal_recommendation": DEAL_RECOMMENDATION,
    
    # Goal notifications
    "goal_created": GOAL_CREATED,
    "goal_progress_update": GOAL_PROGRESS_UPDATE,
    "goal_completed": GOAL_COMPLETED,
    "goal_deadline_approaching": GOAL_DEADLINE_APPROACHING,
    
    # Price alert notifications
    "price_drop_alert": PRICE_DROP_ALERT,
    "price_increase_alert": PRICE_INCREASE_ALERT,
    "special_promotion": SPECIAL_PROMOTION,
    # Remove reference to custom template
    # "special_promotion": SPECIAL_PROMOTION_CUSTOM,
    "flash_deal": FLASH_DEAL,
    
    # Token notifications
    "token_balance_change": TOKEN_BALANCE_CHANGE,
    "token_reward": TOKEN_REWARD,
    "token_expiration_warning": TOKEN_EXPIRATION_WARNING,
    "token_usage_opportunity": TOKEN_USAGE_OPPORTUNITY,
    
    # Market notifications
    "market_new": NEW_MARKET_ADDED,
    "market_status_change": MARKET_STATUS_CHANGE,
    "market_trend": MARKET_TREND,
    "market_opportunity": MARKET_OPPORTUNITY,
} 