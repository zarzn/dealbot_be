from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User, UserCreate, UserInDB
from core.services.auth import (
    authenticate_user,
    create_tokens,
    get_current_user,
    Token,
    TokenData,
    verify_password,
    get_password_hash,
    create_magic_link_token,
    verify_magic_link_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from core.services.notifications import notification_service
from core.database import get_db
from core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    RateLimitExceededError,
    EmailNotVerifiedError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    token_balance: float = Field(ge=0.0)
    created_at: datetime
    email_verified: bool

class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str
    grant_type: str = "password"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class NewPasswordRequest(BaseModel):
    token: str
    new_password: str

class MagicLinkRequest(BaseModel):
    email: EmailStr

class SocialLoginRequest(BaseModel):
    provider: str
    token: str

@router.post("/register", response_model=UserResponse)
async def register(
    user: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Register a new user."""
    # Check if user already exists
    existing_user = await User.get_by_email(db, user.email)
    if existing_user:
        raise InvalidCredentialsError("Email already registered")

    # Create user
    hashed_password = get_password_hash(user.password)
    user_data = UserCreate(
        email=user.email,
        password=hashed_password,
        name=user.name
    )
    
    db_user = await User.create(db, **user_data.model_dump())

    # Send verification email
    verification_token = await create_magic_link_token({"sub": user.email})
    background_tasks.add_task(
        notification_service.send_verification_email,
        user.email,
        verification_token
    )

    return UserResponse(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        token_balance=db_user.token_balance,
        created_at=db_user.created_at,
        email_verified=db_user.email_verified
    )

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Traditional email/password login"""
    try:
        user = await authenticate_user(form_data.username, form_data.password, db)
        if not user:
            raise InvalidCredentialsError("Invalid email or password")
            
        if not user.email_verified:
            raise EmailNotVerifiedError("Please verify your email first")
            
        access_token, refresh_token = await create_tokens({"sub": str(user.id)})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except (AccountLockedError, RateLimitExceededError) as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except EmailNotVerifiedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/magic-link", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    request: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Request magic link login"""
    try:
        user = await User.get_by_email(db, request.email)
        if not user:
            # Don't reveal if user exists
            return {"message": "If an account exists, you will receive a magic link"}
            
        token = create_magic_link_token({"sub": user.email})
        await notification_service.send_magic_link_email(
            email=user.email,
            token=token,
            background_tasks=background_tasks
        )
        
        return {"message": "Magic link sent to your email"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/verify-magic-link", response_model=Token)
async def verify_magic_link(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Verify magic link and login"""
    try:
        payload = verify_magic_link_token(token)
        user = await User.get_by_email(db, payload.get("sub"))
        if not user:
            raise InvalidCredentialsError("Invalid token")
            
        access_token, refresh_token = await create_tokens({"sub": user.email})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link"
        )

@router.post("/reset-password", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    request: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset"""
    try:
        user = await User.get_by_email(db, request.email)
        if not user:
            # Don't reveal if user exists
            return {"message": "If an account exists, you will receive a reset link"}
            
        token = create_password_reset_token({"sub": user.email})
        await notification_service.send_password_reset_email(
            email=user.email,
            token=token,
            background_tasks=background_tasks
        )
        
        return {"message": "Password reset instructions sent to your email"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/new-password")
async def set_new_password(
    request: NewPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set new password using reset token"""
    try:
        payload = verify_password_reset_token(request.token)
        user = await User.get_by_email(db, payload["sub"])
        if not user:
            raise InvalidCredentialsError("Invalid token")
            
        hashed_password = get_password_hash(request.new_password)
        await user.update(db, password=hashed_password)
        
        return {"message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

@router.post("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address"""
    try:
        payload = verify_magic_link_token(token)
        user = await User.get_by_email(db, payload.get("sub"))
        if not user:
            raise InvalidCredentialsError("Invalid token")
            
        await user.update(db, email_verified=True)
        
        return {"message": "Email verified successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link"
        )

@router.post("/social/{provider}", response_model=Token)
async def social_login(
    provider: str,
    request: SocialLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Social login with various providers"""
    try:
        # Verify token with provider
        user_info = await verify_social_token(provider, request.token)
        
        # Get or create user
        user = await User.get_by_email(db, user_info.email)
        if not user:
            user = await User.create(db,
                email=user_info.email,
                name=user_info.name,
                password=None,  # Social users don't have password
                email_verified=True,  # Social emails are pre-verified
                social_provider=provider,
                social_id=user_info.id
            )
            
        access_token, refresh_token = await create_tokens({"sub": user.email})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with {provider}"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Get new access token using refresh token"""
    try:
        payload = verify_refresh_token(refresh_token)
        user = await User.get_by_email(db, payload.get("sub"))
        if not user:
            raise InvalidCredentialsError("Invalid token")
            
        access_token, new_refresh_token = await create_tokens({"sub": user.email})
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired refresh token"
        ) 