"""Token expiration tasks.

This module provides a Celery task for checking tokens that are about to expire and sending
notifications to users.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from uuid import UUID

from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

from core.config import get_settings
from core.models.token import Token
from core.models.user import User
from core.models.enums import NotificationPriority
from core.models.token import TokenStatus
from core.utils.logger import get_logger
from core.celery import celery_app
from core.notifications import TemplatedNotificationService

logger = logging.getLogger(__name__)

# Create synchronous engine and session factory
settings = get_settings()
engine = create_engine(str(settings.sync_database_url))
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Session:
    """Get synchronous database session."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

@celery_app.task(
    name="check_expiring_tokens",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="1/h"
)
def check_expiring_tokens(
    self,
    days_threshold: int = 7,
    skip_notification: bool = False
) -> Dict[str, Any]:
    """Check for tokens that are about to expire and send notifications.
    
    Args:
        days_threshold: Number of days before expiration to send warning
        skip_notification: If True, only log expiring tokens without sending notifications
        
    Returns:
        Dict with task result information
    """
    db = get_db()
    try:
        # Calculate the expiration threshold date
        expiration_threshold = datetime.utcnow() + timedelta(days=days_threshold)
        
        # Get active tokens that expire within the threshold and haven't been notified yet
        # Tokens with NULL expiration date are not included
        tokens = db.query(Token).join(User, Token.user_id == User.id).filter(
            and_(
                Token.status == TokenStatus.ACTIVE.value,
                Token.expires_at.isnot(None),
                Token.expires_at <= expiration_threshold,
                Token.expires_at > datetime.utcnow(),
                Token.last_notification_at.is_(None) | 
                (datetime.utcnow() - Token.last_notification_at > timedelta(days=1))
            )
        ).all()
        
        if not tokens:
            return {
                "status": "success",
                "message": "No expiring tokens found",
                "processed": 0
            }
            
        # Track users with expiring tokens
        user_tokens = {}
        for token in tokens:
            if token.user_id not in user_tokens:
                user_tokens[token.user_id] = []
            user_tokens[token.user_id].append(token)
            
        # Send notifications to users (one notification per user, listing all expiring tokens)
        notifications_sent = 0
        for user_id, tokens in user_tokens.items():
            # Get days until expiration for each token
            token_details = []
            for token in tokens:
                days_left = (token.expires_at - datetime.utcnow()).days
                token_details.append({
                    "id": str(token.id),
                    "name": token.name or "Unnamed Token",
                    "days_left": days_left,
                    "expires_at": token.expires_at.strftime("%Y-%m-%d")
                })
            
            # Sort token details by days left (ascending)
            token_details.sort(key=lambda x: x["days_left"])
            
            if not skip_notification:
                # Create notification service
                notification_service = TemplatedNotificationService(db)
                
                # Get user
                user = db.query(User).get(user_id)
                if not user:
                    logger.warning(f"User {user_id} not found for token expiration notification")
                    continue
                
                # Format total token value
                total_value = sum(token.balance for token in tokens)
                
                # Determine notification priority based on urgency
                closest_expiry = min(token.expires_at for token in tokens)
                days_to_closest_expiry = (closest_expiry - datetime.utcnow()).days
                
                priority = NotificationPriority.MEDIUM
                if days_to_closest_expiry <= 2:
                    priority = NotificationPriority.HIGH
                
                # Create template parameters
                template_params = {
                    "token_count": len(tokens),
                    "total_value": float(total_value),
                    "earliest_expiry": closest_expiry.strftime("%Y-%m-%d"),
                    "days_left": days_to_closest_expiry
                }
                
                # Send notification
                try:
                    notification_service.send_notification(
                        template_id="token_expiration_warning",
                        user_id=user_id,
                        template_params=template_params,
                        override_priority=priority,
                        metadata={
                            "token_count": len(tokens),
                            "total_value": float(total_value),
                            "token_details": token_details,
                            "days_threshold": days_threshold
                        },
                        action_url="/tokens"
                    )
                    
                    notifications_sent += 1
                    
                    # Update last_notification_at for all tokens
                    for token in tokens:
                        token.last_notification_at = datetime.utcnow()
                    
                    logger.info(
                        f"Sent token expiration notification to user {user_id}",
                        extra={
                            "user_id": str(user_id),
                            "token_count": len(tokens),
                            "days_threshold": days_threshold
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send token expiration notification to user {user_id}: {str(e)}",
                        extra={"user_id": str(user_id)}
                    )
        
        # Commit changes to database
        if not skip_notification:
            db.commit()
        
        return {
            "status": "success",
            "message": f"Token expiration check completed, sent {notifications_sent} notifications",
            "processed": len(tokens),
            "notifications_sent": notifications_sent
        }
        
    except Exception as e:
        if not skip_notification:
            db.rollback()
        logger.error(f"Error in token expiration check task: {str(e)}")
        self.retry(exc=e)
    finally:
        db.close() 