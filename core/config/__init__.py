"""Configuration module.

This module provides configuration settings for the application.
"""

import os
import logging
from functools import lru_cache
from typing import Dict, Any

# Try to load AWS environment variables before importing settings
try:
    from .aws_settings import load_aws_environment_variables, is_aws_environment
    
    # Load AWS environment variables if running in AWS
    if is_aws_environment():
        logging.getLogger(__name__).info("Loading AWS environment variables")
        load_aws_environment_variables()
except ImportError:
    logging.getLogger(__name__).warning("AWS settings module not available")

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
