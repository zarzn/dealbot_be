"""Goal-related tasks."""

from typing import Optional, List
from uuid import UUID
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.models.goal_types import GoalStatus
from core.services.token_service import TokenService
from core.exceptions.base_exceptions import BaseError as CoreBaseError
from core.exceptions.goal_exceptions import GoalProcessingError
from core.models.database import Goal as GoalModel
from sqlalchemy.future import select
from sqlalchemy import update

logger = logging.getLogger(__name__)

async def process_goals(
    user_id: UUID,
    goals: List[GoalModel],
    db: Optional[AsyncSession] = None
) -> None:
    """Process goals for a user."""
    db_to_close: Optional[AsyncSession] = None
    try:
        if db is None:
            db_to_close = await get_db()
            db = db_to_close

        # Process each goal
        for goal in goals:
            try:
                # Update goal status
                await update_goal_analytics(goal.id, user_id, db)
                
                # Process notifications
                await process_goal_notifications(goal.id, user_id, db)
                
            except Exception as e:
                logger.error(f"Error processing goal {goal.id}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in process_goals: {str(e)}")
        if db:
            await db.rollback()
    finally:
        if db_to_close:
            await db_to_close.close()

async def update_goal_analytics(
    goal_id: UUID,
    user_id: UUID,
    db: Optional[AsyncSession] = None
) -> None:
    """Update goal analytics."""
    db_to_close: Optional[AsyncSession] = None
    try:
        if db is None:
            db_to_close = await get_db()
            db = db_to_close
            
        # Get the goal
        result = await db.execute(
            select(GoalModel)
            .where(GoalModel.id == goal_id)
            .where(GoalModel.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for analytics update")
            return
            
        # Update analytics
        # TODO: Implement analytics update logic
        
    except Exception as e:
        logger.error(f"Error updating goal analytics: {str(e)}")
        if db:
            await db.rollback()
    finally:
        if db_to_close:
            await db_to_close.close()

async def cleanup_completed_goals(
    days_old: int = 60,
    db: Optional[AsyncSession] = None
) -> None:
    """Clean up old completed goals."""
    db_to_close: Optional[AsyncSession] = None
    try:
        if db is None:
            db_to_close = await get_db()
            db = db_to_close
            
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Get old completed goals
        result = await db.execute(
            select(GoalModel)
            .where(GoalModel.status == GoalStatus.COMPLETED.value)
            .where(GoalModel.updated_at <= cutoff_date)
        )
        goals = result.scalars().all()
        
        # Archive goals
        for goal in goals:
            goal.is_archived = True
            goal.archived_at = datetime.utcnow()
            
        await db.commit()
        logger.info(f"Archived {len(goals)} old completed goals")
        
    except Exception as e:
        logger.error(f"Error cleaning up completed goals: {str(e)}")
        if db:
            await db.rollback()
    finally:
        if db_to_close:
            await db_to_close.close()

async def process_goal_notifications(
    goal_id: UUID,
    user_id: UUID,
    db: Optional[AsyncSession] = None
) -> None:
    """Process notifications for a goal."""
    db_to_close: Optional[AsyncSession] = None
    try:
        if db is None:
            db_to_close = await get_db()
            db = db_to_close
            
        # Get the goal
        result = await db.execute(
            select(GoalModel)
            .where(GoalModel.id == goal_id)
            .where(GoalModel.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for notification processing")
            return
            
        # Process notifications
        # TODO: Implement notification processing logic
        
    except Exception as e:
        logger.error(f"Error processing goal notifications: {str(e)}")
        if db:
            await db.rollback()
    finally:
        if db_to_close:
            await db_to_close.close()
