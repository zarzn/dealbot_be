"""Model relationships module.

This module defines all SQLAlchemy relationships between models to avoid circular dependencies.
"""

from sqlalchemy.orm import relationship

def setup_relationships():
    """Set up all model relationships."""
    from .user import User
    from .goal import Goal
    from .chat import ChatMessage
    from .notification import Notification
    from .token import TokenTransaction, TokenBalanceHistory, TokenWallet
    
    # User relationships
    User.goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    User.notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    User.chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    User.token_transactions = relationship("TokenTransaction", back_populates="user", cascade="all, delete-orphan")
    User.token_balance_history = relationship("TokenBalanceHistory", back_populates="user", cascade="all, delete-orphan")
    User.token_wallets = relationship("TokenWallet", back_populates="user", cascade="all, delete-orphan")
    User.referrals = relationship("User", backref="referred_by_user", remote_side=[User.id])
    
    # Goal relationships
    Goal.user = relationship("User", back_populates="goals")
    Goal.deals = relationship("Deal", back_populates="goal", cascade="all, delete-orphan")
    Goal.notifications = relationship("Notification", back_populates="goal", cascade="all, delete-orphan")
    
    # ChatMessage relationships
    ChatMessage.user = relationship("User", back_populates="chat_messages")
    
    # Notification relationships
    Notification.user = relationship("User", back_populates="notifications")
    Notification.goal = relationship("Goal", back_populates="notifications")
    
    # Token relationships
    TokenTransaction.user = relationship("User", back_populates="token_transactions")
    TokenBalanceHistory.user = relationship("User", back_populates="token_balance_history")
    TokenWallet.user = relationship("User", back_populates="token_wallets") 