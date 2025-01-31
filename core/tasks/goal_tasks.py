from typing import Optional
from uuid import UUID
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.models.goal import GoalUpdate
from backend.core.services.goal import GoalService
from backend.core.exceptions import GoalProcessingError

logger = logging.getLogger(__name__)

async def update_goal_status_task(
    goal_id: UUID,
    user_id: UUID,
    db: Optional[AsyncSession] = None
) -> None:
    """Background task to update goal status based on conditions"""
    try:
        if db is None:
            db = await get_db()
            
        goal_service = GoalService(db)
        goal = await goal_service.get_goal(user_id, goal_id)
        
        if not goal:
            logger.warning(f"Goal {goal_id} not found for status update")
            return
            
        # Check if goal has expired
        if goal.deadline and datetime.utcnow() > goal.deadline:
            await goal_service.update_goal_status(user_id, goal_id, "expired")
            logger.info(f"Goal {goal_id} marked as expired")
            return
            
        # Add other status update logic here
        
    except Exception as e:
        logger.error(f"Failed to update goal status: {str(e)}")
        raise GoalProcessingError(f"Failed to update goal status: {str(e)}")
    finally:
        if db:
            await db.close() 