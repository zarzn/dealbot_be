"""Deal service module.

This module provides a compatibility layer for the deal service.
The actual implementation has been modularized and moved to the deal/ directory.
"""

from .deal.base import DealService

__all__ = ['DealService']

