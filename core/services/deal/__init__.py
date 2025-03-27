"""Deal service package.

This package provides deal-related services for the AI Agentic Deals System.
"""

# Import the DealService class directly from base
from .base import DealService

# Note: The other files (core.py, monitoring.py, etc.) contain functions that 
# are imported into DealService in base.py, not classes to be inherited from.

__all__ = ["DealService"] 