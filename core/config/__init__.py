"""Configuration module for the AI Agentic Deals System."""

from functools import lru_cache
from typing import Union

from .base import BaseConfig
from .development import DevelopmentConfig
from .production import ProductionConfig
from .test import TestSettings

@lru_cache()
def get_settings() -> Union[BaseConfig, TestSettings]:
    """Get configuration settings based on environment."""
    import os
    env = os.getenv("ENVIRONMENT", "development")
    
    if env == "production":
        return ProductionConfig()
    elif env == "test":
        return TestSettings()
    
    return DevelopmentConfig()

settings = get_settings()

__all__ = ['settings', 'get_settings', 'BaseConfig']
