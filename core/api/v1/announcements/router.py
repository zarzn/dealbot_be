"""API router for announcement management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from core.models.announcement import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementResponse,
    AnnouncementType,
    AnnouncementStatus
)
from core.models.user import User
from core.services.announcement import AnnouncementService
from core.api.deps import get_current_user
from core.exceptions.base_exceptions import NotFoundError, ValidationError

router = APIRouter()


@router.post("/", response_model=AnnouncementResponse)
async def create_announcement(
    announcement: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new announcement.
    
    This endpoint requires admin privileges.
    """
    # Check if user has admin privileges
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create announcements"
        )
    
    announcement_service = AnnouncementService(db)
    
    try:
        return await announcement_service.create_announcement(
            data=announcement,
            user_id=current_user.id
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[AnnouncementResponse])
async def get_announcements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[AnnouncementStatus] = None,
    type: Optional[AnnouncementType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a list of announcements.
    
    Admin users can see all announcements.
    Regular users can only see published and archived announcements.
    """
    announcement_service = AnnouncementService(db)
    
    # For non-admin users, only show published and archived announcements
    if current_user.role != "admin" and status is None:
        result = []
        
        # Get published announcements
        published = await announcement_service.get_announcements(
            skip=skip,
            limit=limit,
            status=AnnouncementStatus.PUBLISHED,
            type=type
        )
        result.extend(published)
        
        # Get archived announcements if we have space left in our limit
        if len(result) < limit:
            archived = await announcement_service.get_announcements(
                skip=max(0, skip - len(published)) if skip > 0 else 0,
                limit=limit - len(result),
                status=AnnouncementStatus.ARCHIVED,
                type=type
            )
            result.extend(archived)
            
        return result
    else:
        # Admin can see all announcements or filter by status
        return await announcement_service.get_announcements(
            skip=skip,
            limit=limit,
            status=status,
            type=type
        )


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: UUID = Path(..., title="The ID of the announcement to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific announcement by ID.
    
    Admin users can access any announcement.
    Regular users can only access published and archived announcements.
    """
    announcement_service = AnnouncementService(db)
    
    try:
        announcement = await announcement_service.get_announcement(announcement_id)
        
        # Check access permissions for non-admin users
        if current_user.role != "admin":
            if announcement.status not in [
                AnnouncementStatus.PUBLISHED.value,
                AnnouncementStatus.ARCHIVED.value
            ]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this announcement"
                )
                
        return announcement
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement: AnnouncementUpdate,
    announcement_id: UUID = Path(..., title="The ID of the announcement to update"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an announcement.
    
    This endpoint requires admin privileges.
    """
    # Check if user has admin privileges
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update announcements"
        )
    
    announcement_service = AnnouncementService(db)
    
    try:
        return await announcement_service.update_announcement(
            announcement_id=announcement_id,
            data=announcement,
            user_id=current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: UUID = Path(..., title="The ID of the announcement to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an announcement.
    
    This endpoint requires admin privileges.
    """
    # Check if user has admin privileges
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete announcements"
        )
    
    announcement_service = AnnouncementService(db)
    
    try:
        await announcement_service.delete_announcement(announcement_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_announcement(
    announcement_id: UUID = Path(..., title="The ID of the announcement to publish"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Publish an announcement.
    
    This endpoint requires admin privileges.
    Publishing an announcement will send notifications to targeted users.
    """
    # Check if user has admin privileges
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to publish announcements"
        )
    
    announcement_service = AnnouncementService(db)
    
    try:
        return await announcement_service.publish_announcement(
            announcement_id=announcement_id,
            user_id=current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) 