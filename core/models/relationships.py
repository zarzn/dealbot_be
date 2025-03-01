"""Model relationships module.

This module sets up all SQLAlchemy model relationships to avoid circular imports.
"""

from sqlalchemy.orm import relationship, backref

def setup_relationships():
    """Set up all model relationships."""
    from core.models.user import User
    from core.models.deal import Deal
    from core.models.goal import Goal
    from core.models.price_tracking import PricePoint, PriceTracker
    from core.models.price_prediction import PricePrediction
    from core.models.market import Market
    from core.models.notification import Notification
    from core.models.chat import ChatMessage
    from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet, TokenBalance
    from core.models.deal_score import DealScore
    from core.models.user_preferences import UserPreferences
    from core.models.tracked_deal import TrackedDeal
    from core.models.deal_interaction import DealInteraction

    # Deal relationships
    Deal.user = relationship("User", back_populates="deals")
    Deal.goal = relationship("Goal", back_populates="deals")
    Deal.market = relationship("Market", back_populates="deals")
    Deal.price_points = relationship("PricePoint", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_predictions = relationship("PricePrediction", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_histories = relationship("PriceHistory", back_populates="deal", cascade="all, delete-orphan")
    Deal.scores = relationship("DealScore", back_populates="deal", cascade="all, delete-orphan")
    Deal.notifications = relationship("Notification", back_populates="deal", cascade="all, delete-orphan")
    Deal.trackers = relationship("TrackedDeal", back_populates="deal", cascade="all, delete-orphan")
    Deal.interactions = relationship("DealInteraction", back_populates="deal", cascade="all, delete-orphan")
    Deal.price_trackers = relationship("PriceTracker", back_populates="deal", cascade="all, delete-orphan")

    # Market relationships
    Market.deals = relationship("Deal", back_populates="market", cascade="all, delete-orphan")
    Market.price_histories = relationship("PriceHistory", back_populates="market", cascade="all, delete-orphan")

    # Goal relationships
    Goal.user = relationship("User", back_populates="goals")
    Goal.deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")
    Goal.notifications = relationship("Notification", back_populates="goal", cascade="all, delete-orphan")

    # User relationships
    User.deals = relationship("Deal", back_populates="user")
    User.goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    User.notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    User.preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    User.chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    User.token_transactions = relationship("TokenTransaction", back_populates="user", cascade="all, delete-orphan")
    User.token_balance_history = relationship("TokenBalanceHistory", back_populates="user", cascade="all, delete-orphan")
    User.token_wallet = relationship("TokenWallet", back_populates="user", uselist=False, cascade="all, delete-orphan", overlaps="token_wallets")
    User.token_balance = relationship("TokenBalance", back_populates="user", uselist=False, cascade="all, delete-orphan")
    User.referrals = relationship(
        "User",
        primaryjoin="User.id==User.referred_by",
        back_populates="referred_by_user"
    )
    User.referred_by_user = relationship(
        "User",
        primaryjoin="User.referred_by==User.id",
        remote_side="User.id",
        back_populates="referrals"
    )
    User.price_predictions = relationship("PricePrediction", back_populates="user", cascade="all, delete-orphan")
    User.tracked_deals = relationship("TrackedDeal", back_populates="user", cascade="all, delete-orphan")
    # User.market_users = relationship("MarketUser", back_populates="user")  # MarketUser model not defined
    User.deal_interactions = relationship("DealInteraction", back_populates="user")
    User.price_trackers = relationship("PriceTracker", back_populates="user", cascade="all, delete-orphan")

    # DealInteraction relationships
    DealInteraction.user = relationship("User", back_populates="deal_interactions")
    DealInteraction.deal = relationship("Deal", back_populates="interactions")

    # Price prediction relationships
    PricePrediction.deal = relationship("Deal", back_populates="price_predictions")

    # Token relationships
    TokenTransaction.user = relationship("User", back_populates="token_transactions")
    TokenBalanceHistory.user = relationship("User", back_populates="token_balance_history")
    TokenWallet.user = relationship("User", back_populates="token_wallets", overlaps="token_wallet")
    TokenBalance.user = relationship("User", back_populates="token_balance")

    # Deal score relationships
    DealScore.deal = relationship("Deal", back_populates="scores")

    # ChatMessage relationships
    ChatMessage.user = relationship("User", back_populates="chat_messages")

    # Notification relationships
    Notification.user = relationship("User", back_populates="notifications")
    Notification.goal = relationship("Goal", back_populates="notifications")
    Notification.deal = relationship("Deal", back_populates="notifications")

    # UserPreferences relationships
    UserPreferences.user = relationship("User", back_populates="preferences")

    # TrackedDeal relationships
    TrackedDeal.user = relationship("User", back_populates="tracked_deals")
    TrackedDeal.deal = relationship("Deal", back_populates="trackers")

    # PriceTracker relationships
    PriceTracker.user = relationship("User", back_populates="price_trackers")
    PriceTracker.deal = relationship("Deal", back_populates="price_trackers") 