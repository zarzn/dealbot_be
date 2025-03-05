"""Social authentication service module.

This module provides functionality for social authentication with various providers.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel
import aiohttp
import logging
from datetime import datetime

from core.config import settings
from core.exceptions import SocialAuthError
from core.utils.logger import get_logger

logger = get_logger(__name__)

class SocialUserInfo(BaseModel):
    """Social user information model."""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str

async def verify_google_token(token: str) -> Optional[SocialUserInfo]:
    """Verify Google OAuth token.
    
    Args:
        token: Google OAuth token
        
    Returns:
        SocialUserInfo if token is valid
        
    Raises:
        SocialAuthError: If token verification fails
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            ) as response:
                if response.status != 200:
                    raise SocialAuthError("Invalid Google token", provider="google")
                    
                data = await response.json()
                return SocialUserInfo(
                    id=data["sub"],
                    email=data["email"],
                    name=data.get("name"),
                    picture=data.get("picture"),
                    provider="google"
                )
    except aiohttp.ClientError as e:
        logger.error(f"Google token verification failed: {str(e)}")
        raise SocialAuthError("Google authentication failed: Network error", provider="google")

async def verify_facebook_token(token: str) -> Optional[SocialUserInfo]:
    """Verify Facebook OAuth token.
    
    Args:
        token: Facebook OAuth token
        
    Returns:
        SocialUserInfo if token is valid
        
    Raises:
        SocialAuthError: If token verification fails
    """
    try:
        async with aiohttp.ClientSession() as session:
            # First verify the token
            async with session.get(
                f"https://graph.facebook.com/debug_token?input_token={token}&access_token={settings.FACEBOOK_APP_TOKEN}"
            ) as response:
                if response.status != 200:
                    raise SocialAuthError("Invalid Facebook token", provider="facebook")
                    
                data = await response.json()
                if not data.get("data", {}).get("is_valid"):
                    raise SocialAuthError("Invalid Facebook token", provider="facebook")
                    
            # Then get user info
            async with session.get(
                f"https://graph.facebook.com/me?fields=id,email,name,picture&access_token={token}"
            ) as response:
                if response.status != 200:
                    raise SocialAuthError("Failed to get Facebook user info", provider="facebook")
                    
                data = await response.json()
                
                # Check if email is provided
                if "email" not in data:
                    raise SocialAuthError("Email not provided by Facebook", provider="facebook")
                
                return SocialUserInfo(
                    id=data["id"],
                    email=data["email"],
                    name=data.get("name"),
                    picture=data.get("picture", {}).get("data", {}).get("url"),
                    provider="facebook"
                )
    except aiohttp.ClientError as e:
        logger.error(f"Facebook token verification failed: {str(e)}")
        raise SocialAuthError("Facebook authentication failed: Network error", provider="facebook")

async def verify_social_token(provider: str, token: str) -> Optional[SocialUserInfo]:
    """Verify social OAuth token.
    
    Args:
        provider: Social provider name
        token: OAuth token
        
    Returns:
        SocialUserInfo if token is valid
        
    Raises:
        SocialAuthError: If token verification fails or provider is not supported
    """
    provider_map = {
        "google": verify_google_token,
        "facebook": verify_facebook_token
    }
    
    verify_func = provider_map.get(provider.lower())
    if not verify_func:
        raise SocialAuthError(f"Unsupported social provider: {provider}")
        
    try:
        return await verify_func(token)
    except SocialAuthError:
        raise
    except Exception as e:
        logger.error(f"Social token verification failed: {str(e)}")
        raise SocialAuthError(f"Failed to verify {provider} token") 