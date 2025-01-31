from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID

from backend.core.models.goal import GoalCreate, GoalResponse
from backend.core.services.goal import GoalService
from backend.core.services.token import TokenService
from backend.api.v1.dependencies import (
    get_goal_service,
    get_token_service,
    get_current_active_user
)

router = APIRouter(prefix="/goals", tags=["goals"])

async def validate_tokens(
    token_service: TokenService,
    user_id: UUID,
    operation: str
):
    """Validate user has sufficient tokens for the operation"""
    try:
        await token_service.validate_operation(user_id, operation)
    except Exception as e:
        raise HTTPException(
            status_code=402,
            detail=f"Token validation failed: {str(e)}"
        )

@router.post("/", response_model=GoalResponse)
async def create_goal(
    goal: GoalCreate,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    try:
        # Validate tokens before creating goal
        await validate_tokens(token_service, current_user["id"], "create_goal")
        
        # Create goal and deduct tokens
        created_goal = await goal_service.create_goal(goal)
        await token_service.deduct_tokens(
            current_user["id"],
            "create_goal",
            goal_id=created_goal.id
        )
        return created_goal
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[GoalResponse])
async def get_goals(
    goal_service: GoalService = Depends(get_goal_service),
    current_user: dict = Depends(get_current_active_user)
):
    try:
        return await goal_service.get_goals(user_id=current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    goal: GoalCreate,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    try:
        # Validate tokens before updating goal
        await validate_tokens(token_service, current_user["id"], "update_goal")
        
        # Update goal and deduct tokens
        updated_goal = await goal_service.update_goal(goal_id, goal)
        await token_service.deduct_tokens(
            current_user["id"],
            "update_goal",
            goal_id=goal_id
        )
        return updated_goal
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: UUID,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    try:
        # Validate tokens before deleting goal
        await validate_tokens(token_service, current_user["id"], "delete_goal")
        
        # Delete goal and deduct tokens
        await goal_service.delete_goal(goal_id)
        await token_service.deduct_tokens(
            current_user["id"],
            "delete_goal",
            goal_id=goal_id
        )
        return {"message": "Goal deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
