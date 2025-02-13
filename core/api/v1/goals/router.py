"""Goals API module."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from core.models.goal import (
    GoalCreate,
    GoalResponse,
    GoalAnalytics,
    GoalTemplate,
    GoalShare,
    GoalTemplateCreate,
    GoalShareResponse
)
from core.services.goal import GoalService
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.api.v1.dependencies import (
    get_goal_service,
    get_token_service,
    get_analytics_service,
    get_current_active_user
)

router = APIRouter(tags=["goals"])

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
    """Create a new goal.
    
    Args:
        goal: Goal data
        goal_service: Goal service instance
        token_service: Token service instance
        current_user: Current authenticated user
        
    Returns:
        GoalResponse: Created goal details
        
    Raises:
        HTTPException: If token validation fails or goal creation fails
    """
    try:
        await validate_tokens(token_service, current_user["id"], "create_goal")
        return await goal_service.create_goal(current_user["id"], goal)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Goal creation failed: {str(e)}"
        )

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

@router.get("/{goal_id}/analytics", response_model=GoalAnalytics)
async def get_goal_analytics(
    goal_id: UUID,
    time_range: Optional[str] = Query(
        "7d",
        description="Time range for analytics (1d, 7d, 30d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Get analytics for a specific goal"""
    try:
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "1d": now - timedelta(days=1),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        analytics = await analytics_service.get_goal_analytics(
            goal_id=goal_id,
            user_id=current_user["id"],
            start_date=start_date
        )
        return analytics
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{goal_id}/share", response_model=GoalShareResponse)
async def share_goal(
    goal_id: UUID,
    share_data: GoalShare,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Share a goal with other users"""
    try:
        # Validate tokens before sharing
        await validate_tokens(token_service, current_user["id"], "share_goal")
        
        # Share goal and deduct tokens
        share_result = await goal_service.share_goal(
            goal_id=goal_id,
            user_id=current_user["id"],
            share_with=share_data.share_with,
            permissions=share_data.permissions
        )
        await token_service.deduct_tokens(
            current_user["id"],
            "share_goal",
            goal_id=goal_id
        )
        return share_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/templates", response_model=List[GoalTemplate])
async def get_goal_templates(
    category: Optional[str] = None,
    goal_service: GoalService = Depends(get_goal_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Get available goal templates"""
    try:
        templates = await goal_service.get_templates(
            user_id=current_user["id"],
            category=category
        )
        return templates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/templates", response_model=GoalTemplate)
async def create_goal_template(
    template: GoalTemplateCreate,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new goal template"""
    try:
        # Validate tokens before creating template
        await validate_tokens(token_service, current_user["id"], "create_template")
        
        # Create template and deduct tokens
        created_template = await goal_service.create_template(
            user_id=current_user["id"],
            template=template
        )
        await token_service.deduct_tokens(
            current_user["id"],
            "create_template",
            template_id=created_template.id
        )
        return created_template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/templates/{template_id}", response_model=GoalResponse)
async def create_goal_from_template(
    template_id: UUID,
    goal_service: GoalService = Depends(get_goal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Create a goal from a template"""
    try:
        # Validate tokens before creating goal from template
        await validate_tokens(token_service, current_user["id"], "create_goal")
        
        # Create goal from template and deduct tokens
        created_goal = await goal_service.create_from_template(
            template_id=template_id,
            user_id=current_user["id"]
        )
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

@router.get("/shared", response_model=List[GoalResponse])
async def get_shared_goals(
    goal_service: GoalService = Depends(get_goal_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Get goals shared with the current user"""
    try:
        shared_goals = await goal_service.get_shared_goals(current_user["id"])
        return shared_goals
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shared/{goal_id}/users", response_model=List[GoalShareResponse])
async def get_goal_shared_users(
    goal_id: UUID,
    goal_service: GoalService = Depends(get_goal_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Get users with whom a goal is shared"""
    try:
        shared_users = await goal_service.get_shared_users(goal_id)
        return shared_users
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{goal_id}/share/{user_id}")
async def remove_goal_share(
    goal_id: UUID,
    user_id: UUID,
    goal_service: GoalService = Depends(get_goal_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Remove a user's access to a shared goal"""
    try:
        await goal_service.remove_share(
            goal_id=goal_id,
            owner_id=current_user["id"],
            user_id=user_id
        )
        return {"message": "Share removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/progress", response_model=List[GoalAnalytics])
async def get_goals_progress(
    time_range: Optional[str] = Query(
        "7d",
        description="Time range for progress (1d, 7d, 30d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: dict = Depends(get_current_active_user)
):
    """Get progress analytics for all goals"""
    try:
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "1d": now - timedelta(days=1),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        progress = await analytics_service.get_goals_progress(
            user_id=current_user["id"],
            start_date=start_date
        )
        return progress
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 