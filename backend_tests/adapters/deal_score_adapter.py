"""Deal score adapter for tests.

This module provides adapters for the deal score tests to work with the current implementation.
"""

from core.models.deal_score import DealScore
from core.models.mock_enums import ScoreType

# Patch the DealScore module to include ScoreType
# This is a monkey patch to make the tests work without changing them
import sys
import core.models.deal_score
sys.modules['core.models.deal_score'].ScoreType = ScoreType
