"""Agent type definitions.

This module defines the different types of agents available in the system.
"""

from enum import Enum

class AgentType(str, Enum):
    """Agent type enumeration."""
    MARKET = "market"
    DEAL = "deal"
    GOAL = "goal"
    COORDINATOR = "coordinator"
    CUSTOM = "custom"
    MARKET_ANALYST = "market_analyst"
    DEAL_NEGOTIATOR = "deal_negotiator"
    RISK_ASSESSOR = "risk_assessor" 