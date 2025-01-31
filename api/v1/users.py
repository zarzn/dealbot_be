from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User, UserCreate, UserInDB
from core.services.auth import (
    authenticate_user,
    create_tokens,
    get_current_user,
    Token,
    TokenData,
    redis
)
from core.database import get_db
from core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    RateLimitExceededError
)

router = APIRouter(prefix="/users", tags=["users"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    token_balance: float = Field(ge=0.0)
    created_at: datetime

@router.post("/register", response_model=UserResponse)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Register a new user with proper validation and error handling"""
    try:
        # Check if user already exists
        existing_user = await User.get_by_email(db, user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create new user
        new_user = await User.create(db, **user.dict())
        
        return UserResponse(
            id=str(new_user.id),
            email=new_user.email,
            token_balance=float(new_user.token_balance),
            created_at=new_user.created_at
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/login", response_model=Token)
async def login_user(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Authenticate user and return JWT tokens"""
    try:
        user = await authenticate_user(email, password, redis)
        if not user:
            raise InvalidCredentialsError("Invalid email or password")
            
        access_token, refresh_token = await create_tokens({"sub": user.email})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer"
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Get current authenticated user's profile"""
    try:
        user = await User.get_by_email(db, current_user.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        return UserResponse(
            id=str(user.id),
            email=user.email,
            token_balance=float(user.token_balance),
            created_at=user.created_at
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
