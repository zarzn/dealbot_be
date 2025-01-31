"""Models package.

This module exports all models and their Pydantic schemas for the AI Agentic Deals System.
"""

# Base models
from .base import Base
from .database import BaseRepository, get_db

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
    Deal, DealBase, DealCreate, DealUpdate, DealResponse,
    DealStatus, DealSource, DealScore, PriceHistory
)

# Token models
from .token import (
    TokenTransaction, TokenWallet,
    TransactionType, TransactionStatus,
    TransactionCreate, TransactionUpdate, TransactionResponse,
    TokenWalletCreate, TokenWalletResponse
)

# Market models
from .market import (
    Market, MarketCreate, MarketUpdate, MarketResponse,
    MarketType, MarketStatus, MarketCategory, MarketStats
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
    DealScore, DealScoreCreate, DealScoreUpdate, DealScoreResponse
)

__all__ = [
    # Base
    'Base',
    'BaseRepository',
    'get_db',

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
    'DealBase',
    'DealCreate',
    'DealUpdate',
    'DealResponse',
    'DealStatus',
    'DealSource',
    'DealScore',
    'PriceHistory',

    # Token
    'TokenTransaction',
    'TokenWallet',
    'TransactionType',
    'TransactionStatus',
    'TransactionCreate',
    'TransactionUpdate',
    'TransactionResponse',
    'TokenWalletCreate',
    'TokenWalletResponse',

    # Market
    'Market',
    'MarketCreate',
    'MarketUpdate',
    'MarketResponse',
    'MarketType',
    'MarketStatus',
    'MarketCategory',
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
