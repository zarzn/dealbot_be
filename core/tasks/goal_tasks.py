"""Goal processing tasks."""

from typing import Optional, List
from uuid import UUID
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, update, and_
from sqlalchemy.orm import Session, sessionmaker
from core.config import get_settings
from core.models.goal_types import GoalStatus
from core.services.token_service import TokenService
from core.exceptions.base_exceptions import BaseError as CoreBaseError
from core.exceptions.goal_exceptions import GoalProcessingError
from core.models.database import Goal as GoalModel
from core.celery import celery_app

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

@celery_app.task(bind=True)
def process_goals(self, user_id: str, goal_ids: List[str]) -> None:
    """Process goals for a user."""
    db = get_db()
    try:
        # Get goals from database
        goals = db.query(GoalModel).filter(
            and_(
                GoalModel.id.in_([UUID(gid) for gid in goal_ids]),
                GoalModel.user_id == UUID(user_id)
            )
        ).all()

        # Process each goal
        for goal in goals:
            try:
                # Update goal status
                update_goal_analytics(goal.id, user_id)
                
                # Process notifications
                process_goal_notifications(goal.id, user_id)
                
            except Exception as e:
                logger.error(f"Error processing goal {goal.id}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in process_goals: {str(e)}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(bind=True)
def update_goal_analytics(self, goal_id: str, user_id: str) -> None:
    """Update goal analytics."""
    db = get_db()
    try:
        # Get the goal
        goal = db.query(GoalModel).filter(
            and_(
                GoalModel.id == UUID(goal_id),
                GoalModel.user_id == UUID(user_id)
            )
        ).first()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for analytics update")
            return
            
        # Update analytics
        # TODO: Implement analytics update logic
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error updating goal analytics: {str(e)}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(bind=True)
def cleanup_completed_goals(self, days_old: int = 60) -> None:
    """Clean up old completed goals."""
    db = get_db()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Get old completed goals
        goals = db.query(GoalModel).filter(
            and_(
                GoalModel.status == GoalStatus.COMPLETED.value,
                GoalModel.updated_at <= cutoff_date
            )
        ).all()
        
        # Archive goals
        for goal in goals:
            goal.is_archived = True
            goal.archived_at = datetime.utcnow()
            
        db.commit()
        logger.info(f"Archived {len(goals)} old completed goals")
        
    except Exception as e:
        logger.error(f"Error cleaning up completed goals: {str(e)}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(bind=True)
def process_goal_notifications(self, goal_id: str, user_id: str) -> None:
    """Process notifications for a goal."""
    db = get_db()
    try:
        # Get the goal
        goal = db.query(GoalModel).filter(
            and_(
                GoalModel.id == UUID(goal_id),
                GoalModel.user_id == UUID(user_id)
            )
        ).first()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for notification processing")
            return
            
        # Process notifications
        # TODO: Implement notification processing logic
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error processing goal notifications: {str(e)}")
        db.rollback()
    finally:
        db.close()
