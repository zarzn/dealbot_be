"""Configuration module.

This module provides configuration settings for the application.
"""

from functools import lru_cache
from typing import Dict, Any

from .settings import Settings

__all__ = ['Settings', 'get_settings', 'settings']

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Returns:
        Settings: Application settings
    """
    return Settings()

# Create a global settings instance
settings = get_settings()
