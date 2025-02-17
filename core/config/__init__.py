"""Configuration module for the AI Agentic Deals System."""

import os
from .base import BaseConfig
from .development import DevelopmentConfig
from .production import ProductionConfig
from .test import TestSettings

def get_settings():
    """Get settings based on environment."""
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        return ProductionConfig()
    elif environment == "test":
        return TestSettings()
    
    return DevelopmentConfig()

settings = get_settings()

__all__ = ['settings', 'get_settings', 'BaseConfig']
