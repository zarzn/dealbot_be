"""
Tasks package initialization
"""

from .goal_status import update_goal_status_task
from .goal_tasks import process_goals, update_goal_analytics, cleanup_completed_goals, process_goal_notifications
from .price_monitor import (
    monitor_price_changes,
    update_price_history,
    analyze_price_trends,
    trigger_price_alerts,
    monitor_prices_task,
    process_deal,
    create_price_alert,
    PriceMonitorError,
    NetworkError,
    RateLimitError
)
from .notification_tasks import process_notifications
from .token_tasks import process_token_transactions, update_token_balances, update_token_prices, cleanup_old_transactions

__all__ = [
    # Goal tasks
    'update_goal_status_task',
    'process_goals',
    'update_goal_analytics',
    'cleanup_completed_goals',
    'process_goal_notifications',
    # Price monitoring tasks
    'monitor_price_changes',
    'update_price_history',
    'analyze_price_trends',
    'trigger_price_alerts',
    'monitor_prices_task',
    'process_deal',
    'create_price_alert',
    'PriceMonitorError',
    'NetworkError',
    'RateLimitError',
    # Notification tasks
    'process_notifications',
    # Token tasks
    'process_token_transactions',
    'update_token_balances',
    'update_token_prices',
    'cleanup_old_transactions'
] 