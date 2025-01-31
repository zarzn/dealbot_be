"""
Backend package initialization
"""

__version__ = "0.1.0"

# No imports here to avoid circular dependencies

# Package initialization for backend module
from .config import settings
from .api.v1 import router as api_v1_router

__all__ = ["settings", "api_v1_router"]
