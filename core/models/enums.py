"""Enums module for models.

This module contains all the enum classes used across the models to avoid circular imports.
"""

import enum

class MarketType(str, enum.Enum):
    """Supported market types."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    TARGET = "target"
    BESTBUY = "bestbuy"

class MarketStatus(str, enum.Enum):
    """Market operational statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

class MarketCategory(str, enum.Enum):
    """Market category types."""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    HOME = "home"
    TOYS = "toys"
    BOOKS = "books"
    SPORTS = "sports"
    AUTOMOTIVE = "automotive"
    HEALTH = "health"
    GROCERY = "grocery"
    OTHER = "other" 