"""Models package.

This module exports all models and their Pydantic schemas for the AI Agentic Deals System.
"""

# Base models
from .base import Base
from .database import BaseRepository, get_db

# Enums
from .enums import MarketType, MarketStatus, MarketCategory

# User models
from .user import (
    User, UserBase, UserCreate, UserUpdate, UserResponse,
    UserStatus, NotificationPreference
)

# Goal models
from .goal import (
    Goal, GoalBase, GoalCreate, GoalUpdate, GoalResponse,
    GoalStatus, GoalPriority
)

# Deal models
from .deal import (
    Deal,
    DealCreate,
    DealUpdate,
    DealResponse,
    DealStatus,
    DealSource,
    PriceHistory
)

# Token models
from .token import (
    TokenPrice,
    TokenBalance,
    TokenWallet,
    TokenPriceResponse,
    TokenBalanceResponse,
    TokenWalletCreate,
    TokenWalletUpdate,
    TokenWalletResponse
)
from .token_transaction import (
    TokenTransaction,
    TokenTransactionCreate,
    TokenTransactionUpdate,
    TokenTransactionInDB,
    TransactionType,
    TransactionStatus,
    TransactionResponse,
    TransactionHistoryResponse
)
from .token_balance_history import TokenBalanceHistory
from .token_pricing import TokenPricing

# Market models
from .market import (
    Market, MarketCreate, MarketUpdate, MarketResponse,
    MarketStats
)

# Notification models
from .notification import (
    Notification, NotificationBase, NotificationCreate,
    NotificationUpdate, NotificationResponse,
    NotificationType, NotificationChannel,
    NotificationPriority, NotificationStatus
)

# Deal score models
from .deal_score import (
    DealScore,
    DealScoreCreate,
    DealScoreUpdate,
    DealScoreResponse
)

__all__ = [
    # Base
    'Base',
    'BaseRepository',
    'get_db',

    # Enums
    'MarketType',
    'MarketStatus',
    'MarketCategory',

    # User
    'User',
    'UserBase',
    'UserCreate',
    'UserUpdate',
    'UserResponse',
    'UserStatus',
    'NotificationPreference',

    # Goal
    'Goal',
    'GoalBase',
    'GoalCreate',
    'GoalUpdate',
    'GoalResponse',
    'GoalStatus',
    'GoalPriority',

    # Deal
    'Deal',
    'DealCreate',
    'DealUpdate',
    'DealResponse',
    'DealStatus',
    'DealSource',
    'PriceHistory',

    # Token
    'TokenTransaction',
    'TokenWallet',
    'TokenPrice',
    'TokenBalance',
    'TokenBalanceHistory',
    'TokenPricing',
    'TokenTransactionCreate',
    'TokenTransactionUpdate',
    'TokenTransactionInDB',
    'TransactionType',
    'TransactionStatus',
    'TransactionResponse',
    'TokenWalletCreate',
    'TokenWalletUpdate',
    'TokenWalletResponse',
    'TokenPriceResponse',
    'TokenBalanceResponse',
    'TransactionHistoryResponse',

    # Market
    'Market',
    'MarketCreate',
    'MarketUpdate',
    'MarketResponse',
    'MarketStats',

    # Notification
    'Notification',
    'NotificationBase',
    'NotificationCreate',
    'NotificationUpdate',
    'NotificationResponse',
    'NotificationType',
    'NotificationChannel',
    'NotificationPriority',
    'NotificationStatus',

    # Deal Score
    'DealScore',
    'DealScoreCreate',
    'DealScoreUpdate',
    'DealScoreResponse'
]
