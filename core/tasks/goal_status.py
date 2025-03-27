"""Goal status update tasks."""

from typing import Optional
from uuid import UUID
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from core.database import get_async_db_context
from core.models.database import Goal
from core.models.goal_types import GoalStatus
from core.celery import celery_app

logger = logging.getLogger(__name__)

@celery_app.task
async def update_goal_status_task(
    goal_id: UUID,
    user_id: UUID,
    db: Optional[AsyncSession] = None
) -> None:
    """Background task to update goal status based on conditions"""
    try:
        if db is None:
            # Use the context manager to ensure proper session cleanup
            async with get_async_db_context() as db:
                await _update_goal_status(goal_id, user_id, db)
        else:
            # If session is provided, use it directly
            await _update_goal_status(goal_id, user_id, db)
    except Exception as e:
        logger.error(f"Error updating goal status: {str(e)}")

async def _update_goal_status(goal_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    """Internal function to update goal status logic"""
    try:
        # Get the goal directly from database
        result = await db.execute(
            select(Goal)
            .where(Goal.id == goal_id)
            .where(Goal.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for status update")
            return
            
        # Check if goal has expired
        if goal.deadline and datetime.utcnow() > goal.deadline:
            await db.execute(
                update(Goal)
                .where(Goal.id == goal_id)
                .values(status=GoalStatus.EXPIRED.value, updated_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(f"Goal {goal_id} marked as expired")
            return
    except Exception as e:
        logger.error(f"Error in _update_goal_status: {str(e)}")
        if db:
            await db.rollback()
        # Re-raise to allow the outer function to handle it
        raise 