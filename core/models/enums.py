"""Enums module for models.

This module contains all the enum classes used across the models to avoid circular imports.
"""

from enum import Enum, auto

class MarketType(str, Enum):
    """Market type enum."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    TARGET = "target"
    BESTBUY = "bestbuy"

class MarketStatus(str, Enum):
    """Market status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

class MarketCategory(str, Enum):
    """Market category types."""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    HOME = "home"
    TOYS = "toys"
    BOOKS = "books"
    SPORTS = "sports"
    AUTOMOTIVE = "automotive"
    HEALTH = "health"
    BEAUTY = "beauty"
    GROCERY = "grocery"
    OTHER = "other"

class GoalPriority(str, Enum):
    """Goal priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class GoalStatus(str, Enum):
    """Goal status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class DealStatus(str, Enum):
    """Deal status enum."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SOLD_OUT = "sold_out"
    INVALID = "invalid"
    DELETED = "deleted"

class DealSource(str, Enum):
    """Deal source enum."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    TARGET = "target"
    BESTBUY = "bestbuy"
    MANUAL = "manual"
    API = "api"
    SCRAPER = "scraper"
    USER = "user"
    AGENT = "agent"

class NotificationType(str, Enum):
    """Notification type enum."""
    SYSTEM = "system"
    DEAL = "deal"
    GOAL = "goal"
    PRICE = "price"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"

class NotificationPriority(str, Enum):
    """Notification priority enum."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class NotificationChannel(str, Enum):
    """Notification channel enum."""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    WEBSOCKET = "websocket"

class NotificationStatus(str, Enum):
    """Notification status enum."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    ERROR = "error"

class Currency(str, Enum):
    """Currency enum."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"

class TokenOperation(str, Enum):
    """Token operation enum."""
    DEDUCTION = "deduction"
    REWARD = "reward"
    REFUND = "refund"
    TRANSFER = "transfer"
    PURCHASE = "purchase" 