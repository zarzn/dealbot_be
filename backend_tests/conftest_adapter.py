"""Test configuration for adapters.

This module configures pytest to load the test adapters before running tests.
"""

import pytest
import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import the adapters
from backend_tests.adapters.deal_score_adapter import *

@pytest.fixture(scope="session", autouse=True)
def load_adapters():
    """Load all test adapters."""
    # This fixture runs automatically before any tests
    pass
