from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from core.database import get_db
from core.models.chat import ChatMessage, ChatResponse
from core.services import AgentService, get_current_user
from core.models.user import UserInDB

router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Send a message to the AI agent"""
    agent_service = AgentService(db)
    return await agent_service.process_message(current_user.id, message)

@router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get chat history for current user"""
    agent_service = AgentService(db)
    return await agent_service.get_chat_history(current_user.id) 