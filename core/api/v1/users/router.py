"""Users API module."""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging
from uuid import uuid4, UUID

from core.database import get_db
from core.services.auth import (
    Token,
    authenticate_user,
    create_tokens,
    refresh_tokens,
    TokenRefreshError,
    get_current_user,
    verify_password,
    get_password_hash
)
from core.services.notifications import notification_service
from core.models.user import UserPreferences, User, UserCreate, UserStatus
from core.exceptions import UserNotFoundError, UserError

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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

class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    sol_address: Optional[str] = None
    referral_code: Optional[str] = None
    token_balance: float
    preferences: Optional[dict] = None
    notification_channels: Optional[list] = None
    status: UserStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_payment_at: Optional[datetime] = None
    active_goals_count: int = 0
    total_deals_found: int = 0
    success_rate: float = 0.0
    total_tokens_spent: float = 0.0
    total_rewards_earned: float = 0.0

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None
        }

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserRegistrationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Login user"""
    try:
        logger.info(f"Login attempt for user: {form_data.username}")
        logger.debug(f"Received form data: username={form_data.username}, password_length={len(form_data.password) if form_data.password else 0}")
        
        user = await authenticate_user(form_data.username, form_data.password, db)
        if not user:
            logger.warning(f"Failed login attempt for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logger.info(f"Successful login for user: {form_data.username}")
        access_token, refresh_token = await create_tokens({"sub": str(user.id)})
        
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
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get current user info"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        sol_address=current_user.sol_address,
        referral_code=current_user.referral_code,
        token_balance=float(current_user.total_tokens_spent),
        preferences=current_user.preferences,
        notification_channels=current_user.notification_channels,
        status=current_user.status,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_payment_at=current_user.last_payment_at,
        active_goals_count=current_user.active_goals_count,
        total_deals_found=current_user.total_deals_found,
        success_rate=float(current_user.success_rate),
        total_tokens_spent=float(current_user.total_tokens_spent),
        total_rewards_earned=float(current_user.total_rewards_earned)
    )

@router.post("/logout")
async def logout(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Logout user"""
    # TODO: Implement token blacklisting
    return {"message": "Successfully logged out"}

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_token(request: TokenRefreshRequest) -> Any:
    """Refresh access token using refresh token"""
    try:
        access_token, refresh_token = await refresh_tokens(request.refresh_token)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer"
        )
    except TokenRefreshError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user profile"""
    return current_user

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

class UserPreferencesUpdate(BaseModel):
    notification_email: Optional[bool] = None
    notification_push: Optional[bool] = None
    notification_sms: Optional[bool] = None
    deal_alert_threshold: Optional[float] = None
    preferred_markets: Optional[list[str]] = None
    preferred_categories: Optional[list[str]] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None

@router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
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
        await user.save(db)
        
        # Send reset email in background
        background_tasks.add_task(
            notification_service.send_password_reset_email,
            user.email,
            reset_token
        )
        
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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Confirm password reset with token"""
    try:
        # Find user by reset token
        user = await User.get_by_reset_token(db, request.token)
        if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
            
        # Update password
        user.password = get_password_hash(request.new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await user.save(db)
        
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
    db: AsyncSession = Depends(get_db)
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
        await user.save(db)

        # Send verification email in background
        background_tasks.add_task(
            notification_service.send_email_verification,
            user.email,
            verification_token
        )
        
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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Confirm email verification"""
    try:
        # Find user by verification token
        user = await User.get_by_email_verification_token(db, token)
        if not user or not user.email_verification_expires or user.email_verification_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
            
        # Update user verification status
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None
        await user.save(db)
        
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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update user profile"""
    try:
        updates = request.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )
        
        updated_user = await User.update(db, current_user.id, updates)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/password")
async def update_password(
    request: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Delete user account"""
    try:
        await User.delete(db, current_user.id)
        return {"message": "Account deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/activity")
async def get_user_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user activity history"""
    try:
        activity = await db.get_user_activity(current_user.id)
        return activity
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/preferences", response_model=UserResponse)
async def update_preferences(
    request: UserPreferencesUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
        await current_user.save(db)
        
        return current_user
    except Exception as e:
        logger.error(f"Preferences update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        ) 