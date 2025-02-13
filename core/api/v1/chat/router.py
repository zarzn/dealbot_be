"""Chat API module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from core.database import get_db
from core.models.chat import (
    ChatMessage,
    ChatResponse,
    ChatHistory,
    ChatAnalytics,
    ChatFilter,
    ChatRequest
)
from core.services.agent import AgentService
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.api.v1.dependencies import (
    get_current_user,
    get_agent_service,
    get_token_service,
    get_analytics_service
)
from core.models.user import UserInDB

router = APIRouter(tags=["chat"])

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

@router.post("/message", response_model=ChatResponse)
async def send_message(
    message: ChatRequest,
    background_tasks: BackgroundTasks,
    agent_service: AgentService = Depends(get_agent_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Send a message to the chat system.
    
    Args:
        message: Message data
        background_tasks: FastAPI background tasks
        agent_service: Agent service instance
        token_service: Token service instance
        current_user: Current authenticated user
        
    Returns:
        ChatResponse: Response from the chat system
        
    Raises:
        HTTPException: If token validation fails or message processing fails
    """
    try:
        await validate_tokens(token_service, current_user.id, "send_message")
        agent_service.set_background_tasks(background_tasks)
        return await agent_service.process_message(current_user.id, message)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Message processing failed: {str(e)}"
        )

@router.get("/history", response_model=List[ChatHistory])
async def get_chat_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    filter_type: Optional[str] = Query(None, description="Filter type (all, questions, answers)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_service: AgentService = Depends(get_agent_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get chat history for current user"""
    try:
        filters = ChatFilter(
            start_date=start_date,
            end_date=end_date,
            filter_type=filter_type
        )
        
        history = await agent_service.get_chat_history(
            user_id=current_user.id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        return history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/analytics", response_model=ChatAnalytics)
async def get_chat_analytics(
    time_range: Optional[str] = Query(
        "7d",
        description="Time range for analytics (1d, 7d, 30d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get chat analytics for current user"""
    try:
        # Validate tokens before getting analytics
        await validate_tokens(token_service, current_user.id, "chat_analytics")
        
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "1d": now - timedelta(days=1),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        analytics = await analytics_service.get_chat_analytics(
            user_id=current_user.id,
            start_date=start_date
        )
        
        # Deduct tokens for analytics request
        await token_service.deduct_tokens(
            current_user.id,
            "chat_analytics"
        )
        
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/history")
async def clear_chat_history(
    agent_service: AgentService = Depends(get_agent_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Clear chat history for current user"""
    try:
        await agent_service.clear_chat_history(current_user.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/feedback")
async def submit_chat_feedback(
    message_id: UUID,
    feedback: str,
    agent_service: AgentService = Depends(get_agent_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Submit feedback for a chat message"""
    try:
        await agent_service.submit_feedback(
            user_id=current_user.id,
            message_id=message_id,
            feedback=feedback
        )
        return {"message": "Feedback submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 