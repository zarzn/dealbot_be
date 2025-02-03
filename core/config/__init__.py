"""Configuration module for the AI Agentic Deals System."""

import os
from functools import lru_cache
from .development import DevelopmentConfig
from .production import ProductionConfig

@lru_cache()
def get_settings():
    """Get settings based on environment."""
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        return ProductionConfig()
    
    return DevelopmentConfig()

settings = get_settings()

__all__ = ['settings', 'get_settings'] 