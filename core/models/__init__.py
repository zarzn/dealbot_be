"""Models package.

This module exports all models and their Pydantic schemas for the AI Agentic Deals System.
"""

# Auth models
from .auth_token import (
    AuthToken,
    AuthTokenCreate,
    AuthTokenUpdate,
    AuthTokenResponse,
    TokenType,
    TokenStatus,
    TokenScope
)

# Base models
from .base import Base

# Enums
from .enums import MarketType, MarketStatus, MarketCategory

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

# Price tracking models
from .price_tracking import (
    PricePoint,
    PriceTracker,
    PricePointBase,
    PricePointCreate,
    PricePointResponse,
    PriceTrackerBase,
    PriceTrackerCreate,
    PriceTrackerResponse,
    PriceTrackerUpdate,
    PriceStatistics
)

# Price prediction models
from .price_prediction import (
    PricePrediction,
    ModelMetrics,
    PricePredictionBase,
    PricePredictionCreate,
    PricePredictionPoint,
    PricePredictionResponse,
    PriceAnalysis,
    ModelPerformance,
    PriceTrend
)

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

# Chat models
from .chat import (
    ChatMessage,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatResponse,
    ChatHistory,
    ChatRequest,
    ChatAnalytics,
    ChatFilter,
    MessageRole,
    MessageStatus
)

__all__ = [
    # Auth
    'AuthToken',
    'AuthTokenCreate',
    'AuthTokenUpdate',
    'AuthTokenResponse',
    'TokenType',
    'TokenStatus',
    'TokenScope',

    # Base
    'Base',

    # Enums
    'MarketType',
    'MarketStatus',
    'MarketCategory',

    # Deal
    'Deal',
    'DealCreate',
    'DealUpdate',
    'DealResponse',
    'DealStatus',
    'DealSource',
    'PriceHistory',

    # Price Tracking
    'PricePoint',
    'PriceTracker',
    'PricePointBase',
    'PricePointCreate',
    'PricePointResponse',
    'PriceTrackerBase',
    'PriceTrackerCreate',
    'PriceTrackerResponse',
    'PriceTrackerUpdate',
    'PriceStatistics',

    # Price Prediction
    'PricePrediction',
    'ModelMetrics',
    'PricePredictionBase',
    'PricePredictionCreate',
    'PricePredictionPoint',
    'PricePredictionResponse',
    'PriceAnalysis',
    'ModelPerformance',
    'PriceTrend',

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
    'DealScoreResponse',

    # Chat
    'ChatMessage',
    'ChatMessageCreate',
    'ChatMessageResponse',
    'ChatResponse',
    'ChatHistory',
    'ChatRequest',
    'ChatAnalytics',
    'ChatFilter',
    'MessageRole',
    'MessageStatus'
]
