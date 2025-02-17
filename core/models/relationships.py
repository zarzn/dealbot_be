"""Model relationships module.

This module sets up all SQLAlchemy model relationships to avoid circular imports.
"""

from sqlalchemy.orm import relationship, backref

def setup_relationships():
    """Set up all model relationships."""
    from core.models.user import User
    from core.models.deal import Deal
    from core.models.goal import Goal
    from core.models.price_tracking import PriceTracker, PricePoint
    from core.models.price_prediction import PricePrediction
    from core.models.market import Market
    from core.models.notification import Notification
    from core.models.chat import ChatMessage
    from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet, TokenBalance
    from core.models.deal_score import DealScore
    from core.models.user_preferences import UserPreferences

    # Deal relationships
    Deal.user = relationship("User", back_populates="deals")
    Deal.goal = relationship("Goal", back_populates="deals")
    Deal.market = relationship("Market", back_populates="deals")
    Deal.price_points = relationship("PricePoint", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_trackers = relationship("PriceTracker", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_predictions = relationship("PricePrediction", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_histories = relationship("PriceHistory", back_populates="deal", cascade="all, delete-orphan")
    Deal.scores = relationship("DealScore", back_populates="deal", cascade="all, delete-orphan")
    Deal.notifications = relationship("Notification", back_populates="deal", cascade="all, delete-orphan")

    # User relationships
    User.goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    User.deals = relationship("Deal", back_populates="user", cascade="all, delete-orphan")
    User.notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    User.notification_preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    User.chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    User.token_transactions = relationship("TokenTransaction", back_populates="user", cascade="all, delete-orphan")
    User.token_balance_history = relationship("TokenBalanceHistory", back_populates="user", cascade="all, delete-orphan")
    User.token_wallets = relationship("TokenWallet", back_populates="user", cascade="all, delete-orphan")
    User.token_balance_obj = relationship("TokenBalance", back_populates="user", uselist=False, cascade="all, delete-orphan")
    User.referrals = relationship("User", backref=backref("referred_by_user", remote_side=[User.id]))
    User.price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")
    User.price_predictions = relationship("PricePrediction", back_populates="user", cascade="all, delete-orphan")

    # UserPreferences relationships
    UserPreferences.user = relationship("User", back_populates="notification_preferences")

    # Goal relationships
    Goal.user = relationship("User", back_populates="goals")
    Goal.deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")
    Goal.notifications = relationship("Notification", back_populates="goal", cascade="all, delete-orphan")

    # Market relationships
    Market.deals = relationship("Deal", back_populates="market", cascade="all, delete-orphan")

    # Price tracking relationships
    PricePoint.deal = relationship("Deal", back_populates="price_points")
    PriceTracker.deal = relationship("Deal", back_populates="price_trackers")
    PriceTracker.user = relationship("User", back_populates="price_trackers")

    # Price prediction relationships
    PricePrediction.deal = relationship("Deal", back_populates="price_predictions")
    PricePrediction.user = relationship("User", back_populates="price_predictions")

    # Token relationships
    TokenTransaction.user = relationship("User", back_populates="token_transactions")
    TokenBalanceHistory.user = relationship("User", back_populates="token_balance_history")
    TokenWallet.user = relationship("User", back_populates="token_wallets")
    TokenBalance.user = relationship("User", back_populates="token_balance_obj")

    # Deal score relationships
    DealScore.deal = relationship("Deal", back_populates="scores")

    # ChatMessage relationships
    ChatMessage.user = relationship("User", back_populates="chat_messages")

    # Notification relationships
    Notification.user = relationship("User", back_populates="notifications")
    Notification.goal = relationship("Goal", back_populates="notifications")
    Notification.deal = relationship("Deal", back_populates="notifications")
    
    # Token relationships
    TokenTransaction.user = relationship("User", back_populates="token_transactions")
    TokenBalanceHistory.user = relationship("User", back_populates="token_balance_history")
    TokenWallet.user = relationship("User", back_populates="token_wallets")
    TokenBalance.user = relationship("User", back_populates="token_balance_obj") 