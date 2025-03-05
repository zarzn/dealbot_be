"""Agent factory module.

This module provides factory methods for creating different types of agents
in the AI Agentic Deals System.
"""

from typing import Dict, Any, Optional, Type, List
import logging

from core.agents.base.base_agent import BaseAgent
from core.agents.base.agent_factory import create_agent as base_create_agent
from core.agents.market_agent import MarketAgent
from core.agents.market_analyst_agent import MarketAnalystAgent
from core.services.llm_service import get_llm_service
from core.agents.agent_types import AgentType
from core.agents.agent_context import AgentContext

logger = logging.getLogger(__name__)

class AgentConfig:
    """Configuration for agent creation."""
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_params: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        tool_map: Optional[Dict[str, Any]] = None
    ):
        """Initialize agent configuration.
        
        Args:
            system_prompt: System prompt for the agent
            temperature: Temperature for LLM generation
            max_tokens: Maximum tokens for LLM generation
            model_params: Additional model parameters
            tools: List of tool names
            tool_map: Map of tool names to implementations
        """
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_params = model_params or {}
        self.tools = tools or []
        self.tool_map = tool_map or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "model_params": self.model_params,
            "tools": self.tools,
            "tool_map": self.tool_map
        }

class AgentFactory:
    """Factory for creating agents."""
    
    def __init__(self, llm_service=None):
        """Initialize agent factory.
        
        Args:
            llm_service: Optional LLM service to use for agents
        """
        self._llm_service = llm_service
        
    async def create_agent(
        self,
        agent_type: str,
        config: Optional[AgentConfig] = None,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> BaseAgent:
        """Create an agent of the specified type.
        
        Args:
            agent_type: Type of agent to create
            config: Agent configuration
            context: Agent context
            **kwargs: Additional parameters
            
        Returns:
            Created agent
        """
        config_dict = config.to_dict() if config else {}
        return await create_agent(agent_type, config_dict, context=context, config_obj=config, **kwargs)

_agent_factory_instance = None

async def get_agent_factory(llm_service=None) -> AgentFactory:
    """Get the singleton agent factory instance.
    
    Args:
        llm_service: Optional LLM service to use for agents
    
    Returns:
        Agent factory instance
    """
    global _agent_factory_instance
    if _agent_factory_instance is None:
        if llm_service is None:
            llm_service = await get_llm_service()
        _agent_factory_instance = AgentFactory(llm_service=llm_service)
    return _agent_factory_instance

async def create_agent(
    agent_type: str,
    config: Optional[Dict[str, Any]] = None,
    context: Optional[AgentContext] = None,
    config_obj: Optional[AgentConfig] = None,
    **kwargs
) -> BaseAgent:
    """Create an agent of the specified type.
    
    Args:
        agent_type: The type of agent to create
        config: Configuration for the agent
        context: Agent context
        config_obj: Original AgentConfig object
        **kwargs: Additional arguments to pass to the agent constructor
        
    Returns:
        An instance of the specified agent type
        
    Raises:
        ValueError: If the agent type is not supported
    """
    if config is None:
        config = {}
    
    if agent_type == AgentType.MARKET.value:
        from core.agents.utils.llm_manager import LLMManager
        llm_manager = LLMManager(**config)
        agent = MarketAgent(llm_manager=llm_manager, context=context, config=config_obj)
        await agent.initialize()
        return agent
    elif agent_type == AgentType.MARKET_ANALYST.value:
        from core.agents.utils.llm_manager import LLMManager
        llm_manager = LLMManager(**config)
        agent = MarketAnalystAgent(llm_manager=llm_manager, context=context, config=config_obj)
        await agent.initialize()
        return agent
    elif agent_type == AgentType.DEAL_NEGOTIATOR.value:
        # Create a mock agent for testing
        from core.agents.utils.llm_manager import LLMManager
        llm_manager = LLMManager(**config)
        agent = MarketAnalystAgent(llm_manager=llm_manager, context=context, config=config_obj)
        agent.agent_type = AgentType.DEAL_NEGOTIATOR
        await agent.initialize()
        return agent
    elif agent_type == AgentType.RISK_ASSESSOR.value:
        # Create a mock agent for testing
        from core.agents.utils.llm_manager import LLMManager
        llm_manager = LLMManager(**config)
        agent = MarketAnalystAgent(llm_manager=llm_manager, context=context, config=config_obj)
        agent.agent_type = AgentType.RISK_ASSESSOR
        await agent.initialize()
        return agent
    else:
        # Use the base agent factory for other agent types
        return await base_create_agent(agent_type=agent_type, config=config, context=context, **kwargs)

def get_available_agent_types() -> List[str]:
    """Get a list of available agent types.
    
    Returns:
        A list of available agent type names
    """
    return [agent_type.value for agent_type in AgentType] 