"""Enums module for models.

This module contains all the enum classes used across the models to avoid circular imports.
"""

from enum import Enum, auto

class MarketType(str, Enum):
    """Market type enum."""
    AMAZON = "amazon"
    WALMART = "walmart"
    EBAY = "ebay"
    GOOGLE_SHOPPING = "google_shopping"
    TARGET = "target"
    BESTBUY = "bestbuy"
    NEWEGG = "newegg"
    CRYPTO = "crypto"
    TEST = "test"

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
    CRITICAL = "critical"  # 5
    URGENT = "urgent"      # 4
    HIGH = "high"          # 3
    MEDIUM = "medium"      # 2
    LOW = "low"            # 1

class GoalStatus(str, Enum):
    """Goal status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"
    ERROR = "error"

class DealStatus(str, Enum):
    """Deal status enum."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
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
    GOOGLE_SHOPPING = "google_shopping"
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
    PRICE_ALERT = "price_alert"
    TOKEN = "token"
    SECURITY = "security"
    MARKET = "market"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value

class NotificationPriority(str, Enum):
    """Notification priority enumeration."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value

class NotificationChannel(str, Enum):
    """Notification channel enum."""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    TELEGRAM = "telegram"
    DISCORD = "discord"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value

class NotificationStatus(str, Enum):
    """Notification status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value

class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    ERROR = "error"

class TaskPriority(str, Enum):
    """Task priority enum."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"

class Currency(str, Enum):
    """Currency enum."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"

class TokenType(str, Enum):
    """Token type enumeration."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"

class TokenStatus(str, Enum):
    """Token status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class TokenScope(str, Enum):
    """Token scope enumeration."""
    FULL = "full"
    LIMITED = "limited"
    READ = "read"
    WRITE = "write"
    RESET = "reset"

class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class TokenOperation(str, Enum):
    """Token operation enum."""
    DEDUCTION = "deduction"
    REWARD = "reward"
    REFUND = "refund"
    TRANSFER = "transfer"
    PURCHASE = "purchase"

class TransactionType(str, Enum):
    """Transaction type enumeration."""
    DEDUCTION = "deduction"
    REWARD = "reward"
    REFUND = "refund"
    SEARCH_PAYMENT = "search_payment"
    SEARCH_REFUND = "search_refund"
    CREDIT = "credit"
    OUTGOING = "outgoing"
    INCOMING = "incoming"

class TransactionStatus(str, Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TokenTransactionType(str, Enum):
    """Token transaction type enumeration."""
    REWARD = "reward"
    DEDUCTION = "deduction"
    REFUND = "refund"
    CREDIT = "credit"

class TokenTransactionStatus(str, Enum):
    """Token transaction status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    """Payment method enumeration."""
    PHANTOM = "phantom"
    STRIPE = "stripe"

class BalanceChangeType(str, Enum):
    """Balance change type enumeration."""
    DEDUCTION = "deduction"
    REWARD = "reward"
    REFUND = "refund"

class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class AIModelType(str, Enum):
    """AI model type enumeration."""
    GPT_3_5 = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    DEEPSEEK = "deepseek"
    MOCK = "mock"
    CUSTOM = "custom" 