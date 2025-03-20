"""Custom notification templates module.

This module contains custom notification templates that extend
the base notification template functionality.
"""

from core.notifications.custom_templates.feature_announcement import FeatureAnnouncementTemplate
from core.notifications.custom_templates.special_promotion import SpecialPromotionTemplate

__all__ = [
    'FeatureAnnouncementTemplate',
    'SpecialPromotionTemplate',
] 