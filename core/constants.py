"""System-wide constants for the AI Agentic Deals System.

This module contains all the constants used across the application,
providing a single source of truth for configuration values.
"""

from enum import Enum
from typing import Final

# API Versioning
API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

# Token Constants
MIN_TOKEN_BALANCE: Final[float] = 1.0
SEARCH_COST: Final[float] = 0.1
GOAL_CREATION_COST: Final[float] = 0.5
NOTIFICATION_COST: Final[float] = 0.05

# Cache TTLs (in seconds)
CACHE_TTL_SHORT: Final[int] = 300  # 5 minutes
CACHE_TTL_MEDIUM: Final[int] = 1800  # 30 minutes
CACHE_TTL_LONG: Final[int] = 86400  # 24 hours
CACHE_TTL_VERY_LONG: Final[int] = 86400  # 24 hours

# Token Cache TTLs
BALANCE_CACHE_TTL: Final[int] = CACHE_TTL_MEDIUM  # 5 minutes
PRICE_CACHE_TTL: Final[int] = CACHE_TTL_SHORT  # 1 minute
TRANSACTION_CACHE_TTL: Final[int] = CACHE_TTL_LONG  # 1 hour
WALLET_CACHE_TTL: Final[int] = CACHE_TTL_LONG  # 1 hour
METRICS_CACHE_TTL: Final[int] = CACHE_TTL_SHORT  # 1 minute

# Cache Key Prefixes
CACHE_KEY_PREFIXES: Final[dict] = {
    "token_balance": "token:balance:",
    "token_price": "token:price:",
    "token_transaction": "token:transaction:",
    "token_wallet": "token:wallet:",
    "token_metrics": "token:metrics:",
    "token_allowance": "token:allowance:",
    "token_rewards": "token:rewards:",
    "token_usage": "token:usage:",
    "token_rate_limit": "token:ratelimit:",
    "token_lock": "token:lock:"
}

# Rate Limiting
RATE_LIMIT_DEFAULT: Final[int] = 60  # requests per minute
RATE_LIMIT_AUTHENTICATED: Final[int] = 120  # requests per minute
RATE_LIMIT_BURST: Final[int] = 50

# Pagination
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
DEFAULT_PAGE: Final[int] = 1

# File Size Limits (in bytes)
MAX_UPLOAD_SIZE: Final[int] = 5 * 1024 * 1024  # 5MB
MAX_AVATAR_SIZE: Final[int] = 2 * 1024 * 1024  # 2MB

# Job Queue Names
class QueueName(str, Enum):
    """Queue names for background tasks."""
    DEFAULT = "default"
    HIGH_PRIORITY = "high-priority"
    NOTIFICATIONS = "notifications"
    MARKET_SYNC = "market-sync"
    DEAL_PROCESSING = "deal-processing"

# Background Task Intervals (in seconds)
TASK_INTERVAL_MARKET_SYNC: Final[int] = 3600  # 1 hour
TASK_INTERVAL_DEAL_CHECK: Final[int] = 300  # 5 minutes
TASK_INTERVAL_PRICE_UPDATE: Final[int] = 900  # 15 minutes
TASK_INTERVAL_CLEANUP: Final[int] = 86400  # 24 hours

# Security Constants
JWT_ALGORITHM: Final[str] = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 30
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7
PASSWORD_MIN_LENGTH: Final[int] = 8
MAX_LOGIN_ATTEMPTS: Final[int] = 5
LOCKOUT_DURATION_MINUTES: Final[int] = 15

# Common Regex Patterns
EMAIL_REGEX: Final[str] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
USERNAME_REGEX: Final[str] = r"^[a-zA-Z0-9_-]{3,16}$"
PASSWORD_REGEX: Final[str] = r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$"
URL_REGEX: Final[str] = r"^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$"

# Deal Processing Constants
PRICE_CHANGE_THRESHOLD: Final[float] = 0.1  # 10% change
DEAL_SCORE_THRESHOLD: Final[float] = 0.7  # Minimum score for a good deal
MAX_DEALS_PER_GOAL: Final[int] = 50
DEAL_EXPIRY_HOURS: Final[int] = 24

# Market Integration Constants
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[int] = 5  # seconds
REQUEST_TIMEOUT: Final[int] = 30  # seconds
MAX_CONCURRENT_REQUESTS: Final[int] = 10

# AI Service Constants
MAX_TOKENS: Final[int] = 4096
TEMPERATURE: Final[float] = 0.7
TOP_P: Final[float] = 0.9
PRESENCE_PENALTY: Final[float] = 0.0
FREQUENCY_PENALTY: Final[float] = 0.0

# Notification Constants
MAX_NOTIFICATIONS_PER_USER: Final[int] = 100
NOTIFICATION_BATCH_SIZE: Final[int] = 50
NOTIFICATION_CLEANUP_DAYS: Final[int] = 30

# Database Constants
DB_POOL_SIZE: Final[int] = 20
DB_MAX_OVERFLOW: Final[int] = 10
DB_POOL_TIMEOUT: Final[int] = 30
DB_POOL_RECYCLE: Final[int] = 1800

# Redis Constants
REDIS_MAX_CONNECTIONS: Final[int] = 10
REDIS_POOL_SIZE: Final[int] = 10
REDIS_TIMEOUT: Final[int] = 10
REDIS_KEY_PREFIX: Final[str] = "deals:"

# Token System
MIN_TOKEN_BALANCE = 1.0
SEARCH_COST = 0.1

# Rate Limiting
RATE_LIMIT_DEFAULT = 60  # requests per minute
RATE_LIMIT_AUTHENTICATED = 120  # requests per minute

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
JWT_ALGORITHM = "HS256"

# Cache TTLs (in seconds)
CACHE_TTL_SHORT = 300  # 5 minutes
CACHE_TTL_MEDIUM = 1800  # 30 minutes
CACHE_TTL_LONG = 86400  # 24 hours

# Deal Analysis
DEAL_SCORE_THRESHOLD = 0.7
PRICE_CHANGE_THRESHOLD = 0.1  # 10% change
MIN_PRICE_HISTORY_POINTS = 3

# Notification Settings
MAX_NOTIFICATIONS_PER_REQUEST = 100
NOTIFICATION_BATCH_SIZE = 50
NOTIFICATION_RETRY_ATTEMPTS = 3

# WebSocket Settings
WS_HEARTBEAT_INTERVAL = 30  # seconds
WS_CONNECTION_TIMEOUT = 60  # seconds
MAX_CONNECTIONS_PER_USER = 5

# API Limits
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
MAX_SEARCH_RESULTS = 50
MAX_CONCURRENT_SEARCHES = 3

# Market Integration
MAX_MARKET_RETRIES = 3
MARKET_TIMEOUT = 30  # seconds
MAX_PRODUCTS_PER_REQUEST = 50

# Background Tasks
TASK_RETRY_DELAY = 60  # seconds
MAX_TASK_RETRIES = 3
TASK_BATCH_SIZE = 100

# File Upload
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
MAX_FILES_PER_REQUEST = 10

# Security
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN = 300  # 5 minutes

# Error Messages
ERROR_INVALID_CREDENTIALS = "Invalid credentials"
ERROR_USER_NOT_FOUND = "User not found"
ERROR_INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
ERROR_INVALID_TOKEN = "Invalid token"
ERROR_TOKEN_EXPIRED = "Token expired"
ERROR_RATE_LIMIT_EXCEEDED = "Rate limit exceeded" 