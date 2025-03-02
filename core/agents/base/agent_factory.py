"""Agent factory implementation for creating different types of agents."""

from typing import Dict, Any, Optional
from core.agents.base.agent_interface import IAgent, IAgentFactory
from core.services.agent import AgentService
from core.services.market_search import MarketSearchService
from core.exceptions import AgentInitializationError

class AgentFactory(IAgentFactory):
    """Concrete implementation of agent factory."""

    async def create_agent(
        self,
        agent_type: str,
        use_crew: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> IAgent:
        """Create an agent of specified type.
        
        Args:
            agent_type: Type of agent to create
            use_crew: Whether to use CrewAI implementation
            config: Optional configuration for the agent
            
        Returns:
            IAgent: Created agent instance
            
        Raises:
            AgentInitializationError: If agent type is not supported
        """
        if config is None:
            config = {}

        if agent_type == "goal":
            return AgentService(db=config.get("db"))
        elif agent_type == "market":
            return MarketSearchService(market_repository=config.get("market_repository"))
        else:
            raise AgentInitializationError(f"Unsupported agent type: {agent_type}")

async def create_agent(
    agent_type: str,
    use_crew: bool = False,
    config: Optional[Dict[str, Any]] = None
) -> IAgent:
    """Standalone function to create an agent of specified type.
    
    This is a convenience function that uses the AgentFactory class.
    
    Args:
        agent_type: Type of agent to create
        use_crew: Whether to use CrewAI implementation
        config: Optional configuration for the agent
        
    Returns:
        IAgent: Created agent instance
        
    Raises:
        AgentInitializationError: If agent type is not supported
    """
    factory = AgentFactory()
    return await factory.create_agent(agent_type, use_crew, config) 