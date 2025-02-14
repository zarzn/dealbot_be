from typing import Optional
from uuid import UUID
import logging
from datetime import datetime
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

async def update_goal_status_task(
    goal_id: UUID,
    user_id: UUID,
    db: Optional[AsyncSession] = None
) -> None:
    """Background task to update goal status based on conditions"""
    db_to_close: Optional[AsyncSession] = None
    try:
        if db is None:
            db_to_close = await get_db()
            db = db_to_close
            
        # Get the goal directly from database
        result = await db.execute(
            select(GoalModel)
            .where(GoalModel.id == goal_id)
            .where(GoalModel.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for status update")
            return
            
        # Check if goal has expired
        if goal.deadline and datetime.utcnow() > goal.deadline:
            await db.execute(
                update(GoalModel)
                .where(GoalModel.id == goal_id)
                .values(status=GoalStatus.EXPIRED.value, updated_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(f"Goal {goal_id} marked as expired")
            return
            
        # Add other status update logic here
        
    except CoreBaseError as e:
        logger.error(f"Failed to update goal status: {str(e)}")
        raise GoalProcessingError(f"Failed to update goal status: {str(e)}") from e
    finally:
        if db_to_close:
            await db_to_close.close()
