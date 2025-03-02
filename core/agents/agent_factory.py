"""Agent factory module.

This module provides factory methods for creating different types of agents
in the AI Agentic Deals System.
"""

from typing import Dict, Any, Optional, Type, List
from enum import Enum
import logging

from core.agents.base.base_agent import BaseAgent
from core.agents.base.agent_factory import create_agent as base_create_agent
from core.agents.market_agent import MarketAgent

logger = logging.getLogger(__name__)

class AgentType(str, Enum):
    """Agent type enumeration."""
    MARKET = "market"
    DEAL = "deal"
    GOAL = "goal"
    COORDINATOR = "coordinator"
    CUSTOM = "custom"

def create_agent(
    agent_type: str,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> BaseAgent:
    """Create an agent of the specified type.
    
    Args:
        agent_type: The type of agent to create
        config: Configuration for the agent
        **kwargs: Additional arguments to pass to the agent constructor
        
    Returns:
        An instance of the specified agent type
        
    Raises:
        ValueError: If the agent type is not supported
    """
    if config is None:
        config = {}
    
    if agent_type == AgentType.MARKET.value:
        return MarketAgent(config=config, **kwargs)
    else:
        # Use the base agent factory for other agent types
        return base_create_agent(agent_type=agent_type, config=config, **kwargs)

def get_available_agent_types() -> List[str]:
    """Get a list of available agent types.
    
    Returns:
        A list of available agent type names
    """
    return [agent_type.value for agent_type in AgentType] 