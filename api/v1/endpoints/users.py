from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.services import (
    Token,
    authenticate_user,
    create_tokens,
    get_current_user
)

router = APIRouter(prefix="/users", tags=["users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserCreate(BaseModel):
    email: str
    password: str
    referral_code: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    token_balance: float
    created_at: str

@router.post("/register")
async def register_user(user: UserCreate):
    # TODO: Implement user registration
    return {"message": "User registration endpoint"}

@router.post("/login", response_model=Token)
async def login(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db)
):
    """Login endpoint"""
    user = await authenticate_user(email, password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, refresh_token = await create_tokens({"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

@router.post("/refresh-token")
async def refresh_token(request: TokenRefreshRequest):
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

@router.get("/profile")
async def get_user_profile(token: str = Depends(oauth2_scheme)):
    # TODO: Implement profile retrieval
    return {"message": "User profile endpoint"}
