"""User service module.

This module provides user-related services and database operations.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User, UserUpdate
from core.models.user_preferences import UserPreferences
from core.exceptions import UserNotFoundError, WalletError, BaseError, DatabaseError
from core.database import get_db, AsyncSessionLocal


async def get_user_by_email(email: str) -> Optional[User]:
    """Retrieve a user by their email address.
    
    Args:
        email: The email address to search for
        
    Returns:
        User if found, None otherwise
        
    Raises:
        DatabaseError: If there's an issue with the database connection
    """
    try:
        session = AsyncSessionLocal()
        try:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalars().first()
        finally:
            await session.close()
    except Exception as e:
        raise DatabaseError(f"Failed to get user by email: {str(e)}")


class UserService:
    """Service for handling user-related operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: UUID) -> User:
        """Get user by ID."""
        user = await self.session.get(User, user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")
        return user

    async def update_user(self, user_id: UUID, user_update: UserUpdate) -> User:
        """Update user information."""
        user = await self.get_user(user_id)
        
        update_data = user_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_user_preferences(self, user_id: UUID) -> UserPreferences:
        """Get user preferences."""
        query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.session.execute(query)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences if none exist
            preferences = UserPreferences(user_id=user_id)
            self.session.add(preferences)
            await self.session.commit()
            await self.session.refresh(preferences)

        return preferences

    async def update_user_preferences(self, user_id: UUID, preferences_data: Dict[str, Any]) -> UserPreferences:
        """Update user preferences."""
        preferences = await self.get_user_preferences(user_id)
        
        for key, value in preferences_data.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)

        preferences.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(preferences)
        return preferences

    async def get_user_wallet(self, user_id: UUID) -> Dict[str, Any]:
        """Get user wallet information."""
        user = await self.get_user(user_id)
        return {
            "wallet_address": user.sol_address,
            "sol_address": user.sol_address,
            "token_balance": user.token_balance,
            "last_payment_at": user.last_payment_at
        }

    async def connect_wallet(self, user_id: UUID, wallet_address: str) -> Dict[str, Any]:
        """Connect wallet to user account."""
        user = await self.get_user(user_id)
        
        # Validate wallet address format
        if not self._is_valid_wallet_address(wallet_address):
            raise WalletError("Invalid wallet address format")

        # Check if wallet is already connected to another user
        query = select(User).where(User.sol_address == wallet_address)
        result = await self.session.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user and existing_user.id != user_id:
            raise WalletError("Wallet already connected to another account")

        user.sol_address = wallet_address
        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)

        return await self.get_user_wallet(user_id)

    async def disconnect_wallet(self, user_id: UUID) -> Dict[str, Any]:
        """Disconnect wallet from user account."""
        user = await self.get_user(user_id)
        
        user.sol_address = None
        user.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(user)

        return await self.get_user_wallet(user_id)

    def _is_valid_wallet_address(self, wallet_address: str) -> bool:
        """Validate wallet address format."""
        # Add your wallet address validation logic here
        # For example, check if it's a valid Ethereum or Solana address format
        return True  # Placeholder implementation
