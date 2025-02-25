from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr

from core.models.enums import UserStatus

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    name: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE

class UserCreate(UserBase):
    """User create schema."""
    password: str

class UserUpdate(UserBase):
    """User update schema."""
    password: Optional[str] = None

class UserResponse(UserBase):
    """User response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    email_verified: bool = False
    active_goals_count: int = 0
    total_deals_found: int = 0
    success_rate: float = 0.0
    total_tokens_spent: float = 0.0
    total_rewards_earned: float = 0.0

    class Config:
        """Pydantic config."""
        from_attributes = True 