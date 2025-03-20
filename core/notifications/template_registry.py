"""Template registry for notification system.

This module imports and registers all notification templates,
including built-in and custom templates.
"""

# Import directly from the templates.py file, not from the package
from core.notifications.templates import (
    NotificationTemplate,
    NOTIFICATION_TEMPLATES,
)

# Import custom templates - now they properly inherit from NotificationTemplate
from core.notifications.custom_templates.feature_announcement import FeatureAnnouncementTemplate
from core.notifications.custom_templates.special_promotion import SpecialPromotionTemplate

# Instantiate custom templates
FEATURE_ANNOUNCEMENT_CUSTOM = FeatureAnnouncementTemplate()
SPECIAL_PROMOTION_CUSTOM = SpecialPromotionTemplate()

# Register custom templates
CUSTOM_TEMPLATES = {
    "feature_announcement": FEATURE_ANNOUNCEMENT_CUSTOM,
    "special_promotion_custom": SPECIAL_PROMOTION_CUSTOM,  # Use a different key to avoid collision
}

# Extend the built-in templates with custom ones
TEMPLATES = {**NOTIFICATION_TEMPLATES, **CUSTOM_TEMPLATES}


def get_template(template_id: str) -> NotificationTemplate:
    """Get a notification template by ID.
    
    Args:
        template_id: The ID of the template to get
        
    Returns:
        The notification template
    """
    template = TEMPLATES.get(template_id)
    if not template:
        # Log warning for missing template
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Template not found: {template_id}")
        
    return template 