from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
from uuid import uuid4

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
from core.services.email import send_password_reset_email, send_verification_email
from core.models.user import UserPreferences, User, UserCreate, UserResponse, UserStatus
from core.exceptions import UserNotFoundError, UserError

router = APIRouter(tags=["users"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

class UserResponse(BaseModel):
    id: str
    email: str
    sol_address: Optional[str] = None
    referral_code: Optional[str] = None
    token_balance: float
    preferences: Optional[dict] = None
    notification_channels: Optional[list] = None
    status: UserStatus
    created_at: str
    updated_at: Optional[str] = None
    last_payment_at: Optional[str] = None
    active_goals_count: int
    total_deals_found: int
    success_rate: float
    total_tokens_spent: float
    total_rewards_earned: float

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserRegistrationRequest, db: AsyncSession = Depends(get_db)) -> Any:
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
            "referral_code": user.referral_code,
            "token_balance": 0.0,
            "status": UserStatus.ACTIVE,
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
            },
            "notification_channels": ["in_app", "email"]
        })
        
        logger.info(f"User created successfully with ID: {new_user.id}")
        
        return UserResponse(
            id=str(new_user.id),
            email=new_user.email,
            sol_address=new_user.sol_address,
            referral_code=new_user.referral_code,
            token_balance=float(new_user.token_balance),
            preferences=new_user.preferences,
            notification_channels=new_user.notification_channels,
            status=new_user.status,
            created_at=str(new_user.created_at),
            updated_at=str(new_user.updated_at) if new_user.updated_at else None,
            last_payment_at=str(new_user.last_payment_at) if new_user.last_payment_at else None,
            active_goals_count=0,
            total_deals_found=0,
            success_rate=0.0,
            total_tokens_spent=0.0,
            total_rewards_earned=0.0
        )
    except HTTPException as he:
        logger.error(f"HTTP Exception during registration: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during registration: {str(e)}"
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
    return current_user

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
        user = await db.get_user_by_email(request.email)
        if user:
            reset_token = await create_password_reset_token(user.id)
            background_tasks.add_task(
                send_password_reset_email,
                email=user.email,
                token=reset_token
            )
        return {"message": "If the email exists, a password reset link will be sent"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Confirm password reset"""
    try:
        user_id = await verify_password_reset_token(request.token)
        user = await db.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        
        hashed_password = get_password_hash(request.new_password)
        await db.update_user_password(user.id, hashed_password)
        
        return {"message": "Password has been reset successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/verify-email/request")
async def request_email_verification(
    request: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Request email verification"""
    try:
        user = await db.get_user_by_email(request.email)
        if user and not user.email_verified:
            verification_token = await create_email_verification_token(user.id)
            background_tasks.add_task(
                send_verification_email,
                email=user.email,
                token=verification_token
            )
        return {"message": "If the email exists and is not verified, a verification link will be sent"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/verify-email/confirm/{token}")
async def confirm_email_verification(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Confirm email verification"""
    try:
        user_id = await verify_email_token(token)
        user = await db.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        
        await db.verify_user_email(user.id)
        return {"message": "Email has been verified successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
        
        updated_user = await db.update_user(current_user.id, updates)
        return UserResponse.from_orm(updated_user)
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
        if not verify_password(request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        hashed_password = get_password_hash(request.new_password)
        await db.update_user_password(current_user.id, hashed_password)
        return {"message": "Password updated successfully"}
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
        await db.delete_user(current_user.id)
        return {"message": "Account deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user preferences"""
    try:
        preferences = await db.get_user_preferences(current_user.id)
        return preferences
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/preferences")
async def update_preferences(
    request: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update user preferences"""
    try:
        updates = request.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )
        
        updated_preferences = await db.update_user_preferences(current_user.id, updates)
        return updated_preferences
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
