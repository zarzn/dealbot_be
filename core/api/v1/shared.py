"""Shared content API endpoints.

This module defines endpoints for viewing shared content, both for
authenticated and unauthenticated users.
"""

import logging
from typing import Optional, List, Dict, Any
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_404_NOT_FOUND, HTTP_403_FORBIDDEN, HTTP_410_GONE
from fastapi.responses import JSONResponse

from core.api.v1.dependencies import get_optional_user, get_db
from core.models.shared_content import SharedContentDetail
from core.models.user import User
from core.services.sharing import SharingService, get_sharing_service
from core.exceptions.share_exceptions import ShareException
from core.utils.json_utils import sanitize_for_json
from core.database import get_async_db_session, get_async_db_context
from core.utils.logger import get_logger

# Use a standard router with no prefix - the main app will mount it correctly
router = APIRouter(tags=["shared"])
logger = get_logger(__name__)

# Create a dependency that uses the context manager approach
async def get_db_session():
    """Get database session using the new context manager pattern."""
    async with get_async_db_context() as session:
        yield session

@router.get("/shared-public/{share_id}", response_model=None)
async def view_shared_content(
    request: Request,
    share_id: str = Path(..., description="ID of the shared content"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """View shared content without requiring authentication.
    
    This endpoint allows public access to view shared content using a share ID.
    It tracks view analytics even for anonymous users.
    """
    logger.info(f"Viewing shared content (public endpoint): {share_id}")
    logger.debug(f"Request path: {request.url.path}, method: {request.method}")
    logger.debug(f"Authenticated user: {current_user.email if current_user else 'Anonymous'}")
    
    try:
        # Extract viewer information for analytics
        viewer_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        referrer = request.headers.get("referer", None)
        
        # Initialize sharing service
        sharing_service = SharingService(db)
        
        # Get the shared content
        # Pass viewer_id if user is authenticated
        result = await sharing_service.get_shared_content(
            share_id=share_id,
            viewer_id=current_user.id if current_user else None,
            viewer_ip=viewer_ip,
            viewer_device=user_agent,
            referrer=referrer
        )
        
        # Log success
        logger.info(f"Successfully retrieved shared content for ID: {share_id}")
        
        # Sanitize result before returning
        sanitized_result = sanitize_for_json(result.model_dump())
        return JSONResponse(content=sanitized_result)
    except ShareException as e:
        logger.error(f"Share error: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        elif "expired" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
        elif "not active" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
        elif "requires authentication" in str(e).lower() or "not authorized" in str(e).lower():
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error viewing shared content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Unexpected error: {str(e)}"
        ) 