"""
Task management module for the AI Agentic Deals System.

This module provides background tasks and scheduled jobs for:
- Processing deals and price monitoring
- Generating notifications
- Updating user goals
- Maintaining token balances
- Analyzing deals using AI
"""

# Import specific task functions for direct access
from core.tasks.price_monitor import (
    monitor_price_changes,
    update_price_history,
    analyze_price_trends,
    trigger_price_alerts,
    monitor_prices_task,
    process_deal,
    create_price_alert
)

from core.tasks.notification_tasks import (
    process_notifications,
    cleanup_old_notifications,
    send_batch_notifications
)

from core.tasks.goal_tasks import (
    process_goals,
    update_goal_analytics,
    cleanup_completed_goals,
    process_goal_notifications
)

from core.tasks.token_tasks import (
    update_token_balances,
    update_token_prices,
    process_token_transactions,
    cleanup_old_transactions
)

from core.tasks.goal_status import update_goal_status_task

from core.tasks.deal_tasks import (
    schedule_batch_deal_analysis,
    process_deal_analysis_task
)

# Public API
__all__ = [
    'monitor_price_changes',
    'update_price_history',
    'analyze_price_trends',
    'trigger_price_alerts',
    'monitor_prices_task',
    'process_deal',
    'create_price_alert',
    'process_notifications',
    'cleanup_old_notifications',
    'send_batch_notifications',
    'process_goals',
    'update_goal_analytics',
    'cleanup_completed_goals',
    'process_goal_notifications',
    'update_token_balances',
    'update_token_prices',
    'process_token_transactions',
    'cleanup_old_transactions',
    'update_goal_status_task',
    'schedule_batch_deal_analysis',
    'process_deal_analysis_task'
] 