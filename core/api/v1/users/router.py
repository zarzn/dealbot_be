"""Users API module."""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Request, Form, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, UUID4
from typing import Optional, Any, Dict, List, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timedelta, timezone, time
import logging
from uuid import uuid4, UUID
from sqlalchemy.exc import SQLAlchemyError
import decimal
import jwt

from core.database import get_db, get_async_db_context
from core.utils.logger import get_logger
from core.dependencies import get_current_user
from core.services.auth import get_password_hash, verify_password, create_access_token, create_refresh_token, AuthService
from core.services.user import UserService, get_user_by_email
from core.models.auth import Token
from core.models.user import UserCreate, UserUpdate, UserResponse, User, UserStatus
from core.models.user_preferences import (
    UserPreferences, UserPreferencesUpdate, UserPreferencesResponse,
    NotificationChannel, Theme, Language, NotificationTimeWindow, NotificationFrequency
)
from core.exceptions.auth_exceptions import TokenRefreshError
from core.exceptions import InvalidCredentialsError
from core.services.notification import NotificationService
from core.models.notification import NotificationType, NotificationChannel, NotificationPriority
from core.notifications import TemplatedNotificationService

router = APIRouter(tags=["auth"])
logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Define get_db_session function for local use
async def get_db_session():
    """
    Get a database session using the async context manager.
    This properly manages connections and prevents leaks.
    """
    async with get_async_db_context() as session:
        yield session

class UserRegistrationRequest(BaseModel):
    """Model for user registration request"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        pattern=r'[A-Za-z\d@$!%*#?&]{8,}',
        description="User password (must be at least 8 characters long and contain letters, numbers, and special characters)"
    )
    referral_code: Optional[str] = Field(
        None,
        min_length=6,
        max_length=10,
        pattern=r'^[A-Z0-9]{6,10}$',
        description="User referral code"
    )
    name: Optional[str] = None

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserRegistrationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Register a new user with proper validation and error handling"""
    try:
        logger.info(f"Starting user registration process for email: {user.email}")
        
        # Check if user already exists
        existing_user = await User.get_by_email(db, user.email)
        if existing_user:
            logger.warning(f"Registration failed: Email already exists: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        logger.info(f"Creating new user with email: {user.email}")
        # Create new user with default values
        new_user = await User.create(db, **{
            "email": user.email,
            "password": get_password_hash(user.password),
            "name": user.name,
            "referral_code": user.referral_code,
            "token_balance": 0.0,
            "status": "active",
            "preferences": {
                "theme": "light",
                "notifications": "all",
                "email_notifications": True,
                "push_notifications": False,
                "telegram_notifications": False,
                "discord_notifications": False,
                "deal_alert_threshold": 0.8,
                "auto_buy_enabled": False,
                "auto_buy_threshold": 0.95,
                "max_auto_buy_amount": 100.0,
                "language": "en",
                "timezone": "UTC"
            }
        })
        
        # Send registration confirmation notification
        notification_service = TemplatedNotificationService(db)
        background_tasks.add_task(
            notification_service.send_registration_confirmation,
            user_id=new_user.id
        )
        
        return new_user
    except Exception as e:
        logger.error(f"Registration failed with error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Login user"""
    try:
        logger.info(f"Login attempt for user: {form_data.username}")
        logger.debug(f"Received form data: username={form_data.username}, password_length={len(form_data.password) if form_data.password else 0}")
        
        auth_service = AuthService(db)
        user = await auth_service.authenticate_user(form_data.username, form_data.password)
        if not user:
            logger.warning(f"Failed login attempt for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logger.info(f"Successful login for user: {form_data.username}")
        # Create tokens
        access_token = await create_access_token({"sub": str(user.id)})
        refresh_token = await create_refresh_token({"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Login error for user {form_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=UserResponse)
async def get_user_me(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Get current user information."""
    # Safely access preferences and notification_channels
    try:
        preferences_data = {}
        notification_channels_data = []
        
        try:
            # Safely attempt to access the preferences property
            preferences_obj = getattr(current_user, 'preferences', None)
            if preferences_obj is not None:
                preferences_data = dict(preferences_obj) if preferences_obj else {}
        except Exception as e:
            logger.warning(f"Error accessing preferences: {str(e)}")
            # Continue with empty preferences
        
        try:
            # Safely attempt to access the notification_channels property
            channels = getattr(current_user, 'notification_channels', None)
            if channels is not None:
                notification_channels_data = list(channels) if channels else []
        except Exception as e:
            logger.warning(f"Error accessing notification_channels: {str(e)}")
            # Continue with empty notification channels
        
        # Create a UserResponse with calculated fields
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            status=current_user.status,
            sol_address=current_user.sol_address,
            referral_code=current_user.referral_code,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            token_balance=float(getattr(current_user, 'token_balance', 0) or 0),
            preferences=preferences_data,
            notification_channels=notification_channels_data,
            last_payment_at=current_user.last_payment_at,
            active_goals_count=int(getattr(current_user, 'active_goals_count', 0) or 0),
            total_deals_found=int(getattr(current_user, 'total_deals_found', 0) or 0),
            success_rate=float(getattr(current_user, 'success_rate', 0) or 0),
            total_tokens_spent=float(getattr(current_user, 'total_tokens_spent', 0) or 0),
            total_rewards_earned=float(getattr(current_user, 'total_rewards_earned', 0) or 0),
            role=getattr(current_user, 'role', 'user'),
            verified=bool(getattr(current_user, 'email_verified', False))
        )
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        # Return a basic response with essential fields to avoid complete failure
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name or "",
            status=current_user.status if hasattr(current_user, 'status') else "active",
            sol_address=current_user.sol_address if hasattr(current_user, 'sol_address') else None,
            referral_code=current_user.referral_code if hasattr(current_user, 'referral_code') else None,
            created_at=current_user.created_at if hasattr(current_user, 'created_at') else datetime.utcnow(),
            updated_at=current_user.updated_at if hasattr(current_user, 'updated_at') else datetime.utcnow(),
            preferences={},
            notification_channels=[],
            token_balance=0.0,
            last_payment_at=None,
            active_goals_count=0,
            total_deals_found=0,
            success_rate=0.0,
            total_tokens_spent=0.0,
            total_rewards_earned=0.0,
            role="user",
            verified=False
        )

@router.post("/logout")
async def logout(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Logout user"""
    # TODO: Implement token blacklisting
    return {"message": "Successfully logged out"}

class TokenRefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Refresh access token using refresh token"""
    try:
        auth_service = AuthService(db)
        tokens = await auth_service.refresh_tokens(request.refresh_token)
        return Token(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=3600  # Assuming 1 hour expiry
        )
    except TokenRefreshError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Get user profile"""
    try:
        # Extract all base scalar attributes directly from the User model
        # This avoids accessing any relationship properties that would trigger
        # async database operations in a synchronous context
        
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name or "",
            status=current_user.status,
            sol_address=current_user.sol_address,
            referral_code=current_user.referral_code,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            last_payment_at=current_user.last_payment_at,
            # Use empty dict/list for relationship fields to avoid async errors
            preferences={},
            notification_channels=[],
            # Use scalar properties only
            active_goals_count=int(getattr(current_user, 'active_goals_count', 0) or 0),
            total_deals_found=int(getattr(current_user, 'total_deals_found', 0) or 0),
            success_rate=float(getattr(current_user, 'success_rate', 0) or 0),
            total_tokens_spent=float(getattr(current_user, 'total_tokens_spent', 0) or 0),
            total_rewards_earned=float(getattr(current_user, 'total_rewards_earned', 0) or 0),
            token_balance=0.0,  # Default value
            role=getattr(current_user, 'role', 'user'),
            verified=bool(getattr(current_user, 'email_verified', False))
        )
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        # Return a basic response with essential fields to avoid complete failure
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name or "",
            status=current_user.status if hasattr(current_user, 'status') else "active",
            sol_address=current_user.sol_address if hasattr(current_user, 'sol_address') else None,
            referral_code=current_user.referral_code if hasattr(current_user, 'referral_code') else None,
            created_at=current_user.created_at if hasattr(current_user, 'created_at') else datetime.utcnow(),
            updated_at=current_user.updated_at if hasattr(current_user, 'updated_at') else datetime.utcnow(),
            preferences={},
            notification_channels=[],
            token_balance=0.0,
            last_payment_at=None,
            active_goals_count=0,
            total_deals_found=0,
            success_rate=0.0,
            total_tokens_spent=0.0,
            total_rewards_earned=0.0,
            role="user",
            verified=False
        )

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class UpdateProfileRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Request password reset"""
    try:
        user = await User.get_by_email(db, request.email)
        if not user:
            # Return success even if user doesn't exist to prevent email enumeration
            return {"message": "If the email exists, a password reset link will be sent"}
            
        # Generate reset token
        reset_token = str(uuid4())
        
        # Store token in user record with expiration
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        await db.commit()
        
        # Send reset email in background
        async def send_password_reset_email(email: str, token: str):
            logger.info(f"Sending password reset email to {email}")
            # In a real implementation, this would send an actual email
            # For testing, we'll just log it
            logger.info(f"Password reset link with token {token} would be sent to {email}")
        
        background_tasks.add_task(send_password_reset_email, user.email, reset_token)
        
        return {"message": "If the email exists, a password reset link will be sent"}
    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Confirm password reset with token"""
    try:
        # Find user by reset token
        result = await db.execute(
            select(User).where(User.reset_token == request.token)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
            
        # Update password
        user.password = get_password_hash(request.new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await db.commit()
        
        # Create notification for password reset using templated service
        notification_service = TemplatedNotificationService(db)
        await notification_service.send_password_reset_notification(
            user_id=user.id
        )
        
        return {"message": "Password successfully reset"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset confirmation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.post("/verify-email/request")
async def request_email_verification(
    request: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Request email verification"""
    try:
        user = await User.get_by_email(db, request.email)
        if not user:
            # Return success even if user doesn't exist to prevent email enumeration
            return {"message": "If the email exists, a verification link will be sent"}

        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
            
        # Generate verification token
        verification_token = str(uuid4())
        
        # Store token in user record with expiration
        user.email_verification_token = verification_token
        user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
        await db.commit()

        # Send verification email in background
        async def send_email_verification(email: str, token: str):
            logger.info(f"Sending email verification to {email}")
            # In a real implementation, this would send an actual email
            # For testing, we'll just log it
            logger.info(f"Email verification link with token {token} would be sent to {email}")
        
        background_tasks.add_task(send_email_verification, user.email, verification_token)
        
        return {"message": "If the email exists, a verification link will be sent"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process email verification request"
        )

@router.post("/verify-email/confirm/{token}")
async def confirm_email_verification(
    token: str,
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Confirm email verification"""
    try:
        # Find user by verification token
        result = await db.execute(
            select(User).where(User.email_verification_token == token)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.email_verification_expires or user.email_verification_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
            
        # Update user verification status
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None
        await db.commit()
        
        return {"message": "Email successfully verified"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification confirmation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email"
        )

@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Update user profile"""
    try:
        updates = request.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )
        
        # Update the current user with the new values
        for key, value in updates.items():
            setattr(current_user, key, value)
        
        current_user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(current_user)
        
        return current_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/password")
async def update_password(
    request: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Update user password"""
    try:
        # Verify current password
        if not verify_password(request.current_password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        hashed_password = get_password_hash(request.new_password)
        await User.update(db, current_user.id, {"password": hashed_password})
        
        # Create notification for password change using templated service
        notification_service = TemplatedNotificationService(db)
        await notification_service.send_password_changed_notification(
            user_id=current_user.id
        )
        
        return {"message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Delete user account"""
    try:
        # Instead of deleting the user, mark them as inactive
        current_user.status = UserStatus.INACTIVE
        current_user.updated_at = datetime.utcnow()
        await db.commit()
        return {"message": "Account deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/activity")
async def get_user_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Get user activity history"""
    try:
        # Query user activity from relevant tables
        # This is a placeholder that would be replaced with actual logic
        # to fetch activity from various sources like goals, deals, etc.
        from sqlalchemy import select
        # Just returning a placeholder response for now
        return {
            "activities": [],
            "total": 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/preferences", response_model=UserResponse)
async def update_preferences(
    request: UserPreferencesUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Update user preferences"""
    try:
        # Update preferences
        preferences = current_user.preferences or {}
        
        if request.notification_email is not None:
            preferences["email_notifications"] = request.notification_email
        if request.notification_push is not None:
            preferences["push_notifications"] = request.notification_push
        if request.notification_sms is not None:
            preferences["sms_notifications"] = request.notification_sms
        if request.deal_alert_threshold is not None:
            preferences["deal_alert_threshold"] = request.deal_alert_threshold
        if request.preferred_markets is not None:
            preferences["preferred_markets"] = request.preferred_markets
        if request.preferred_categories is not None:
            preferences["preferred_categories"] = request.preferred_categories
        if request.currency is not None:
            preferences["currency"] = request.currency
        if request.language is not None:
            preferences["language"] = request.language
        if request.theme is not None:
            preferences["theme"] = request.theme
            
        current_user.preferences = preferences
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        return current_user
    except SQLAlchemyError as e:
        logger.error(f"Database error updating user preferences: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences due to a database error."
        )
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# New endpoints for settings (GET and PATCH)
@router.get("/settings", response_model=UserPreferencesResponse)
async def get_settings(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Get user settings"""
    try:
        # Safely access the user's preferences
        preferences_data = {}
        try:
            # Safely attempt to access the preferences property
            preferences_obj = getattr(current_user, 'preferences', None)
            if preferences_obj is not None:
                preferences_data = dict(preferences_obj) if preferences_obj else {}
        except Exception as e:
            logger.warning(f"Error accessing preferences: {str(e)}")
            # Continue with empty preferences
            
        # Query the user's preferences from the database for a complete model
        try:
            # Get from the UserPreferences model if it exists
            from sqlalchemy import select
            from datetime import time
            
            query = select(UserPreferences).where(UserPreferences.user_id == current_user.id)
            result = await db.execute(query)
            preferences = result.scalar_one_or_none()  # Careful not to await this

            if preferences:
                # Create a complete response with all required fields
                # Prepare notification frequency dictionary for response
                notification_freq = {}
                try:
                    if preferences.notification_frequency:
                        for key, value in preferences.notification_frequency.items():
                            if isinstance(value, dict) and "frequency" in value:
                                notification_freq[key] = value
                            else:
                                # Handle case where value is already a string/enum
                                notification_freq[key] = {"type": key, "frequency": value if isinstance(value, str) else getattr(value, 'value', 'immediate')}
                except Exception as e:
                    logger.warning(f"Error processing notification frequency for response: {str(e)}")
                    # Set default notification frequency if there's an error
                    notification_freq = {
                        "deal": {"type": "deal", "frequency": "immediate"},
                        "goal": {"type": "goal", "frequency": "immediate"},
                        "price_alert": {"type": "price_alert", "frequency": "immediate"},
                        "token": {"type": "token", "frequency": "daily"},
                        "security": {"type": "security", "frequency": "immediate"},
                        "market": {"type": "market", "frequency": "daily"},
                        "system": {"type": "system", "frequency": "immediate"}
                    }
                
                # Convert time windows to the expected format for response
                time_windows_dict = {}
                try:
                    if preferences.time_windows:
                        for channel, window in preferences.time_windows.items():
                            try:
                                channel_enum = NotificationChannel(channel)
                                start_time_val = time(9, 0)  # Default 9am
                                end_time_val = time(21, 0)  # Default 9pm
                                
                                # Safely parse start time
                                if isinstance(window.get("start_time"), str):
                                    try:
                                        start_time_val = time.fromisoformat(window.get("start_time"))
                                    except ValueError:
                                        pass
                                        
                                # Safely parse end time
                                if isinstance(window.get("end_time"), str):
                                    try:
                                        end_time_val = time.fromisoformat(window.get("end_time"))
                                    except ValueError:
                                        pass
                                        
                                time_windows_dict[channel_enum] = NotificationTimeWindow(
                                    start_time=start_time_val,
                                    end_time=end_time_val,
                                    timezone=window.get("timezone", "UTC")
                                )
                            except (ValueError, KeyError) as e:
                                logger.warning(f"Invalid time window data for channel {channel}: {e}")
                except Exception as e:
                    logger.warning(f"Error processing time windows for response: {str(e)}")
                    
                # Ensure we have at least the default time window
                if not time_windows_dict:
                    time_windows_dict[NotificationChannel.IN_APP] = NotificationTimeWindow(
                        start_time=time(9, 0),
                        end_time=time(21, 0),
                        timezone="UTC"
                    )
                
                # Create the response object with safe defaults for all required fields
                muted_until = None
                if preferences.muted_until:
                    try:
                        muted_until = preferences.muted_until.time()
                    except Exception as e:
                        logger.warning(f"Error converting muted_until to time: {str(e)}")
                
                # Create the response object from the database model
                return UserPreferencesResponse(
                    id=preferences.id,
                    user_id=preferences.user_id,
                    theme=Theme(preferences.theme) if preferences.theme else Theme.SYSTEM,
                    language=Language(preferences.language) if preferences.language else Language.EN,
                    timezone=preferences.timezone or "UTC",
                    enabled_channels=[NotificationChannel(ch) for ch in preferences.enabled_channels] if preferences.enabled_channels else [NotificationChannel.IN_APP],
                    notification_frequency=notification_freq,
                    time_windows=time_windows_dict,
                    muted_until=muted_until,
                    do_not_disturb=preferences.do_not_disturb or False,
                    email_digest=preferences.email_digest or False,
                    push_enabled=preferences.push_enabled or False,
                    sms_enabled=preferences.sms_enabled or False,
                    telegram_enabled=preferences.telegram_enabled or False,
                    discord_enabled=preferences.discord_enabled or False,
                    minimum_priority=preferences.minimum_priority or "low",
                    deal_alert_settings=preferences.deal_alert_settings or {},
                    price_alert_settings=preferences.price_alert_settings or {},
                    email_preferences=preferences.email_preferences or {},
                    created_at=preferences.created_at or datetime.now(),
                    updated_at=preferences.updated_at or datetime.now()
                )
        except Exception as e:
            logger.warning(f"Error getting UserPreferences model: {str(e)}")
            # Continue with the fallback approach
        
        # Fallback: Create a complete UserPreferencesResponse with default values
        # We must return a valid UserPreferencesResponse object that meets all the required fields
        user_id = current_user.id
        
        # Default notification frequency
        notification_freq = {
            "deal": {"type": "deal", "frequency": "immediate"},
            "goal": {"type": "goal", "frequency": "immediate"},
            "price_alert": {"type": "price_alert", "frequency": "immediate"},
            "token": {"type": "token", "frequency": "daily"},
            "security": {"type": "security", "frequency": "immediate"},
            "market": {"type": "market", "frequency": "daily"},
            "system": {"type": "system", "frequency": "immediate"}
        }
        
        # Default time windows
        time_windows_dict = {
            NotificationChannel.IN_APP: NotificationTimeWindow(
                start_time=time(9, 0),
                end_time=time(21, 0),
                timezone="UTC"
            ),
            NotificationChannel.EMAIL: NotificationTimeWindow(
                start_time=time(9, 0),
                end_time=time(21, 0),
                timezone="UTC"
            )
        }
        
        # Return a properly structured response with all required fields
        return UserPreferencesResponse(
            id=user_id,
            user_id=user_id,
            theme=Theme(preferences_data.get("theme", "system")),
            language=Language(preferences_data.get("language", "en")),
            timezone=preferences_data.get("timezone", "UTC"),
            enabled_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            notification_frequency=notification_freq,
            time_windows=time_windows_dict,
            muted_until=None,
            do_not_disturb=preferences_data.get("do_not_disturb", False),
            email_digest=preferences_data.get("email_digest", True),
            push_enabled=preferences_data.get("push_notifications", True),
            sms_enabled=preferences_data.get("sms_notifications", False),
            telegram_enabled=preferences_data.get("telegram_notifications", False),
            discord_enabled=preferences_data.get("discord_notifications", False),
            minimum_priority=preferences_data.get("minimum_priority", "low"),
            deal_alert_settings=preferences_data.get("deal_alert_settings", {}),
            price_alert_settings=preferences_data.get("price_alert_settings", {}),
            email_preferences=preferences_data.get("email_preferences", {}),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error retrieving user settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error retrieving settings: {str(e)}"
        )

@router.patch("/settings", response_model=UserPreferencesResponse)
async def update_settings(
    request: UserPreferencesUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Update user settings"""
    try:
        # Query the user's preferences from the database
        query = select(UserPreferences).where(UserPreferences.user_id == current_user.id)
        result = await db.execute(query)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences with all required fields if none exist
            logger.info(f"Creating default preferences for user {current_user.id}")
            preferences = UserPreferences(
                id=uuid4(),
                user_id=current_user.id,
                enabled_channels=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value],
                notification_frequency={
                    "deal": {"type": "deal", "frequency": "immediate"},
                    "goal": {"type": "goal", "frequency": "immediate"},
                    "price_alert": {"type": "price_alert", "frequency": "immediate"},
                    "token": {"type": "token", "frequency": "daily"},
                    "security": {"type": "security", "frequency": "immediate"},
                    "market": {"type": "market", "frequency": "daily"},
                    "system": {"type": "system", "frequency": "immediate"}
                },
                time_windows={
                    "in_app": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"},
                    "email": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"}
                },
                theme=Theme.LIGHT.value,
                language=Language.EN.value,
                timezone="UTC",
                do_not_disturb=False,
                email_digest=True,
                push_enabled=True,
                sms_enabled=False,
                telegram_enabled=False,
                discord_enabled=False,
                minimum_priority="low",
                deal_alert_settings={},
                price_alert_settings={},
                email_preferences={}
            )
            db.add(preferences)
        
        # Update preferences with the new values
        try:
            if request.theme is not None:
                preferences.theme = request.theme.value
            if request.language is not None:
                preferences.language = request.language.value
            if request.timezone is not None:
                preferences.timezone = request.timezone
            if request.enabled_channels is not None:
                preferences.enabled_channels = [ch.value for ch in request.enabled_channels]
            if request.notification_frequency is not None:
                # Convert notification frequency to the right format
                updated_freq = {}
                for notification_type, frequency in request.notification_frequency.items():
                    # Handle different formats of frequency value
                    if isinstance(frequency, dict) and "frequency" in frequency:
                        # Make a copy to avoid modifying the original
                        freq_copy = frequency.copy()
                        # Convert enabled from boolean to string if present
                        if "enabled" in freq_copy and isinstance(freq_copy["enabled"], bool):
                            freq_copy["enabled"] = str(freq_copy["enabled"]).lower()
                        updated_freq[notification_type] = freq_copy
                    elif isinstance(frequency, str) and frequency.lower() in ["immediate", "hourly", "daily", "weekly", "off"]:
                        # Simple string format
                        if frequency.lower() == "off":
                            updated_freq[notification_type] = {
                                "type": notification_type,
                                "frequency": "daily",  # Default to daily when turned off
                                "enabled": "false"  # Convert boolean to string
                            }
                        else:
                            updated_freq[notification_type] = {
                                "type": notification_type,
                                "frequency": frequency.lower()
                            }
                    elif frequency == "off" or (isinstance(frequency, dict) and frequency.get("enabled") is False):
                        # Special case for "off" option
                        updated_freq[notification_type] = {
                            "type": notification_type,
                            "frequency": "daily",  # Default to daily when turned off
                            "enabled": "false"  # Convert boolean to string
                        }
                    elif isinstance(frequency, dict) and "type" in frequency and "frequency" in frequency:
                        # Object with both type and frequency, convert boolean to string
                        freq_copy = frequency.copy()
                        if "enabled" in freq_copy and isinstance(freq_copy["enabled"], bool):
                            freq_copy["enabled"] = str(freq_copy["enabled"]).lower()
                        updated_freq[notification_type] = freq_copy
                    else:
                        # Default fallback
                        updated_freq[notification_type] = {
                            "type": notification_type,
                            "frequency": "immediate"
                        }
                
                # Ensure all 'enabled' values are strings
                for type_key, type_value in updated_freq.items():
                    if isinstance(type_value, dict) and "enabled" in type_value:
                        if isinstance(type_value["enabled"], bool):
                            type_value["enabled"] = str(type_value["enabled"]).lower()
                
                preferences.notification_frequency = updated_freq
            if request.time_windows is not None:
                # Convert time windows to the right format
                updated_windows = {}
                for channel, window in request.time_windows.items():
                    updated_windows[channel.value] = {
                        "start_time": window.start_time.isoformat(),
                        "end_time": window.end_time.isoformat(),
                        "timezone": window.timezone
                    }
                preferences.time_windows = updated_windows
            if request.muted_until is not None:
                # Convert time to datetime with today's date
                today = datetime.now().date()
                muted_until_dt = datetime.combine(today, request.muted_until)
                preferences.muted_until = muted_until_dt
            if request.do_not_disturb is not None:
                preferences.do_not_disturb = request.do_not_disturb
            if request.email_digest is not None:
                preferences.email_digest = request.email_digest
            if request.push_enabled is not None:
                preferences.push_enabled = request.push_enabled
            if request.sms_enabled is not None:
                preferences.sms_enabled = request.sms_enabled
            if request.telegram_enabled is not None:
                preferences.telegram_enabled = request.telegram_enabled
            if request.discord_enabled is not None:
                preferences.discord_enabled = request.discord_enabled
            if request.minimum_priority is not None:
                preferences.minimum_priority = request.minimum_priority
            if request.deal_alert_settings is not None:
                preferences.deal_alert_settings = request.deal_alert_settings
            if request.price_alert_settings is not None:
                preferences.price_alert_settings = request.price_alert_settings
            if request.email_preferences is not None:
                preferences.email_preferences = request.email_preferences
        except Exception as e:
            logger.warning(f"Error updating preference fields: {str(e)}")
            # Continue with commit to save any fields that were successfully updated
        
        # Save changes to the database
        try:
            await db.commit()
            await db.refresh(preferences)
            
            # Send notification for security-related preference changes
            if (request.push_enabled is not None or 
                request.sms_enabled is not None or 
                request.telegram_enabled is not None or 
                request.discord_enabled is not None or
                request.enabled_channels is not None):
                
                # Initialize notification service
                notification_service = TemplatedNotificationService(db)
                
                # Send security settings updated notification
                await notification_service.send_notification(
                    template_id="sec_settings_updated",
                    user_id=current_user.id,
                    metadata={
                        "updated_at": datetime.utcnow().isoformat(),
                        "settings_updated": {
                            "notification_channels": request.enabled_channels is not None,
                            "push_enabled": request.push_enabled is not None,
                            "sms_enabled": request.sms_enabled is not None,
                            "telegram_enabled": request.telegram_enabled is not None,
                            "discord_enabled": request.discord_enabled is not None
                        }
                    }
                )
        except Exception as e:
            await db.rollback()
            logger.error(f"Database error updating preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save preferences: {str(e)}"
            )
        
        # Prepare notification frequency dictionary for response
        notification_freq = {}
        try:
            if preferences.notification_frequency:
                for key, value in preferences.notification_frequency.items():
                    if isinstance(value, dict):
                        # Make a copy to avoid modifying the original
                        val_copy = value.copy()
                        # Convert boolean enabled to string if present
                        if "enabled" in val_copy and not isinstance(val_copy["enabled"], str):
                            val_copy["enabled"] = str(val_copy["enabled"]).lower()
                        notification_freq[key] = val_copy
                    else:
                        # Handle case where value is already a string/enum
                        notification_freq[key] = {
                            "type": key, 
                            "frequency": value if isinstance(value, str) else getattr(value, 'value', 'immediate')
                        }
        except Exception as e:
            logger.warning(f"Error processing notification frequency for response: {str(e)}")
            # Set default notification frequency if there's an error
            notification_freq = {
                "deal": {"type": "deal", "frequency": "immediate"},
                "goal": {"type": "goal", "frequency": "immediate"},
                "price_alert": {"type": "price_alert", "frequency": "immediate"},
                "token": {"type": "token", "frequency": "daily"},
                "security": {"type": "security", "frequency": "immediate"},
                "market": {"type": "market", "frequency": "daily", "enabled": "false"},
                "system": {"type": "system", "frequency": "immediate"}
            }
        
        # Convert time windows to the expected format for response
        time_windows_dict = {}
        try:
            if preferences.time_windows:
                for channel, window in preferences.time_windows.items():
                    try:
                        channel_enum = NotificationChannel(channel)
                        start_time_val = time(9, 0)  # Default 9am
                        end_time_val = time(21, 0)  # Default 9pm
                        
                        # Safely parse start time
                        if isinstance(window.get("start_time"), str):
                            try:
                                start_time_val = time.fromisoformat(window.get("start_time"))
                            except ValueError:
                                pass
                                
                        # Safely parse end time
                        if isinstance(window.get("end_time"), str):
                            try:
                                end_time_val = time.fromisoformat(window.get("end_time"))
                            except ValueError:
                                pass
                                
                        time_windows_dict[channel_enum] = NotificationTimeWindow(
                            start_time=start_time_val,
                            end_time=end_time_val,
                            timezone=window.get("timezone", "UTC")
                        )
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Invalid time window data for channel {channel}: {e}")
        except Exception as e:
            logger.warning(f"Error processing time windows for response: {str(e)}")
            
        # Ensure we have at least the default time window
        if not time_windows_dict:
            time_windows_dict[NotificationChannel.IN_APP] = NotificationTimeWindow(
                start_time=time(9, 0),
                end_time=time(21, 0),
                timezone="UTC"
            )
        
        # Create the response object with safe defaults for all required fields
        muted_until = None
        if preferences.muted_until:
            try:
                muted_until = preferences.muted_until.time()
            except Exception as e:
                logger.warning(f"Error converting muted_until to time: {str(e)}")
        
        # Create the response object
        return UserPreferencesResponse(
            id=preferences.id,
            user_id=preferences.user_id,
            theme=Theme(preferences.theme) if preferences.theme else Theme.SYSTEM,
            language=Language(preferences.language) if preferences.language else Language.EN,
            timezone=preferences.timezone or "UTC",
            enabled_channels=[NotificationChannel(ch) for ch in preferences.enabled_channels] if preferences.enabled_channels else [NotificationChannel.IN_APP],
            notification_frequency=notification_freq,
            time_windows=time_windows_dict,
            muted_until=muted_until,
            do_not_disturb=preferences.do_not_disturb or False,
            email_digest=preferences.email_digest or False,
            push_enabled=preferences.push_enabled or False,
            sms_enabled=preferences.sms_enabled or False,
            telegram_enabled=preferences.telegram_enabled or False,
            discord_enabled=preferences.discord_enabled or False,
            minimum_priority=preferences.minimum_priority or "low",
            deal_alert_settings=preferences.deal_alert_settings or {},
            price_alert_settings=preferences.price_alert_settings or {},
            email_preferences=preferences.email_preferences or {},
            created_at=preferences.created_at or datetime.now(),
            updated_at=preferences.updated_at or datetime.now()
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error updating user settings: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings due to a database error."
        )
    except Exception as e:
        logger.error(f"Error updating user settings: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
