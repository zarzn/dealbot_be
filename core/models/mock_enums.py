"""Mock enums for testing.

This module contains mock implementations of enums that are needed for tests
but are not part of the current implementation.
"""

from enum import Enum

class ScoreType(str, Enum):
    """Mock score type enum for tests."""
    AI = "ai"
    USER = "user"
    SYSTEM = "system"
    COMBINED = "combined"
