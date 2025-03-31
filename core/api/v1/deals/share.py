"""Share API endpoints for deals.

This module defines API endpoints for sharing deals and search results.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_403_FORBIDDEN

from core.models.user import User
from core.models.shared_content import SharedContent, ShareContentRequest, ShareableContentType, ShareVisibility
from core.services.sharing import SharingService
from core.exceptions.share_exceptions import ShareException
from core.api.v1.dependencies import get_current_user, get_optional_user
from core.database import get_async_db_context
from core.utils.logger import get_logger
from core.utils.json_utils import sanitize_for_json
from core.config import settings
from core.utils.auth_utils import log_auth_info, get_authorization_token

router = APIRouter(tags=["Deals Sharing"])
logger = get_logger(__name__)

# Create a dependency that uses the context manager approach
async def get_db_session():
    """Get database session using the new context manager pattern."""
    async with get_async_db_context() as session:
        yield session

@router.post("/share", response_model=None)
async def create_shareable_content(
    request: Request,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """Create a shareable link for a deal or search results."""
    # Log request info
    log_auth_info(request, logger)
    
    # Debug logging for authentication
    logger.info(f"Create shareable content request received")
    logger.info(f"Current user: {current_user.id if current_user else 'Not authenticated'}")
    
    try:
        # Ensure all data is JSON serializable before processing
        sanitized_data = sanitize_for_json(data)
        
        # Convert the input data to a ShareContentRequest object
        share_request = ShareContentRequest(
            content_type=ShareableContentType(sanitized_data.get("content_type")),
            content_id=sanitized_data.get("content_id"),
            search_params=sanitized_data.get("search_params"),
            title=sanitized_data.get("title"),
            description=sanitized_data.get("description"),
            expiration_days=sanitized_data.get("expiration_days"),
            visibility=ShareVisibility(sanitized_data.get("visibility", "public")),
            include_personal_notes=sanitized_data.get("include_personal_notes", False),
            personal_notes=sanitized_data.get("personal_notes")
        )
        
        # Use the frontend URL from settings instead of request's host
        base_url = settings.SITE_URL
        logger.info(f"Using frontend URL from settings: {base_url} for creating shareable content")
        
        # Create the shareable content
        sharing_service = SharingService(db)
        result = await sharing_service.create_shareable_content(
            user_id=current_user.id,
            share_request=share_request,
            base_url=base_url
        )
        
        # Sanitize the result for JSON serialization
        sanitized_result = sanitize_for_json(result.model_dump())
        return JSONResponse(content=sanitized_result, status_code=status.HTTP_201_CREATED)
    except ShareException as e:
        logger.error(f"Error creating shareable content: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating shareable content: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@router.get("/share/content/{share_id}", response_model=None)
async def get_shared_content(
    request: Request,
    share_id: str = Path(..., description="ID of the shared content"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """Get shared content by share ID (authenticated access)."""
    # Log request info
    log_auth_info(request, logger)
    
    try:
        logger.info(f"Getting shared content with ID: {share_id}")
        
        # Get the shared content using the sharing service
        sharing_service = SharingService(db)
        
        # Extract viewer information for analytics
        viewer_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        referrer = request.headers.get("referer", None)
        
        # Retrieve shared content with complete analytics tracking
        result = await sharing_service.get_shared_content(
            share_id=share_id, 
            viewer_id=current_user.id,
            viewer_ip=viewer_ip,
            viewer_device=user_agent,
            referrer=referrer
        )
        
        # Sanitize result before returning
        sanitized_result = sanitize_for_json(result.model_dump())
        return JSONResponse(content=sanitized_result)
    except ShareException as e:
        logger.error(f"Error getting shared content: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting shared content: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@router.get("/share/list", response_model=None)
async def list_user_shares(
    request: Request,
    offset: int = Query(0, description="Pagination offset"),
    limit: int = Query(20, description="Pagination limit"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """List all shared content created by the current user."""
    # Log request info
    log_auth_info(request, logger)
    
    try:
        sharing_service = SharingService(db)
        content_type_enum = ShareableContentType(content_type) if content_type else None
        
        # Use the frontend URL from settings instead of request's host
        base_url = settings.SITE_URL
        logger.info(f"Using frontend URL from settings: {base_url} for listing user shares")
        
        result = await sharing_service.get_user_shared_content(
            user_id=current_user.id,
            offset=offset,
            limit=limit,
            content_type=content_type_enum,
            base_url=base_url
        )
        # Sanitize items for JSON serialization
        sanitized_items = [sanitize_for_json(item.model_dump()) for item in result]
        return JSONResponse(content=sanitized_items)
    except ShareException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing user shares: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@router.get("/share/metrics/{share_id}", response_model=None)
async def get_share_metrics(
    request: Request,
    share_id: str = Path(..., description="ID of the shared content"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """Get engagement metrics for a shared content item."""
    # Log request info
    log_auth_info(request, logger)
    
    try:
        sharing_service = SharingService(db)
        result = await sharing_service.get_metrics(share_id, current_user.id)
        # Sanitize result before returning
        sanitized_result = sanitize_for_json(result.model_dump())
        return JSONResponse(content=sanitized_result)
    except ShareException as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting share metrics: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@router.delete("/share/{share_id}", response_model=None)
async def deactivate_share(
    request: Request,
    share_id: str = Path(..., description="ID of the shared content to deactivate"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """Deactivate a share link."""
    # Log request info
    log_auth_info(request, logger)
    
    try:
        sharing_service = SharingService(db)
        result = await sharing_service.deactivate_share(share_id, current_user.id)
        return JSONResponse(content={"success": True, "message": "Share deactivated successfully"})
    except ShareException as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deactivating share: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")

# Add a simple test endpoint
@router.get("/share/auth-test", response_model=None)
async def auth_test(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """Simple test endpoint to verify authentication is working."""
    # Log request info
    log_auth_info(request, logger)
    
    return JSONResponse(content={
        "authenticated": True,
        "user_id": str(current_user.id),
        "email": current_user.email
    })

# Add a no-auth test endpoint
@router.get("/share/no-auth-test", response_model=None)
async def no_auth_test(
    request: Request
) -> JSONResponse:
    """Test endpoint that doesn't require authentication."""
    # Log request info
    logger.info(f"Request: {request.method} {request.url}")
    auth_header = request.headers.get("Authorization")
    logger.info(f"Auth header present: {'Yes' if auth_header else 'No'}")
    
    return JSONResponse(content={
        "message": "This endpoint doesn't require authentication",
        "auth_header_present": auth_header != "None",
        "auth_header": auth_header
    })

@router.get("/share/auth-debug", response_model=None)
async def auth_debug_endpoint(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    """Debug endpoint to check authentication status and headers.
    
    This endpoint doesn't require authentication and will return
    the current state of authentication for troubleshooting purposes.
    """
    logger.info(f"Auth debug request: {request.method} {request.url}")
    
    # Check request headers and authentication status
    headers = dict(request.headers.items())
    
    # Mask sensitive data in headers for logging and response
    masked_headers = {}
    for k, v in headers.items():
        if k.lower() in ['authorization', 'cookie']:
            masked_headers[k] = f"{v[:10]}..." if v else None
        else:
            masked_headers[k] = v
    
    # Log headers for debugging
    logger.info(f"Request headers: {json.dumps(masked_headers)}")
    
    # Extract auth header
    auth_header = request.headers.get("Authorization")
    
    # Extract token if present
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        # Only show the first 10 characters for security
        token_display = token[:10] + "..." if token else None
    else:
        token_display = None
    
    # Check for cookies
    cookies = {k: "present" for k in request.cookies}
    
    # Check if current_user was automatically injected
    user_authenticated = current_user is not None
    
    # Check for access token in request params (not recommended but sometimes used)
    access_token_param = request.query_params.get('access_token')
    
    # Try to load localStorage from a hidden field if sent from frontend
    # (This is just for debugging - the frontend would need to send this)
    
    # Compile auth debug info
    auth_info = {
        "authenticated": user_authenticated,
        "user_id": str(current_user.id) if user_authenticated else None,
        "email": current_user.email if user_authenticated else None,
        "auth_header_present": auth_header is not None,
        "token_present": token is not None,
        "token_display": token_display,
        "cookies": cookies,
        "access_token_in_params": access_token_param is not None,
        "headers": masked_headers
    }
    
    # Log authorization details
    logger.info(f"Auth status: {'Authenticated' if user_authenticated else 'Not authenticated'}")
    if user_authenticated:
        logger.info(f"Authenticated user: {current_user.email} ({current_user.id})")
    
    return JSONResponse(content=auth_info)

@router.post("/share/api-test", response_model=None)
async def api_test_endpoint(
    request: Request,
    data: Dict[str, Any] = None
) -> JSONResponse:
    """Test endpoint for API functionality without requiring authentication.
    
    This endpoint accepts any data and returns it along with request details.
    It's useful for testing API connectivity and basic request/response flow.
    """
    logger.info(f"API test request: {request.method} {request.url}")
    
    # Get headers (masked for security)
    masked_headers = {}
    for k, v in request.headers.items():
        if k.lower() in ['authorization', 'cookie']:
            masked_headers[k] = f"{v[:10]}..." if v else None
        else:
            masked_headers[k] = v
    
    # Extract auth header
    auth_header = request.headers.get("Authorization")
    
    # Build response data
    response_data = {
        "success": True,
        "received_data": data,
        "request_info": {
            "method": request.method,
            "url": str(request.url),
            "auth_header_present": auth_header is not None,
            "content_type": request.headers.get("Content-Type")
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        content=response_data,
        status_code=status.HTTP_200_OK
    ) 