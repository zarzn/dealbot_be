"""Agent adapter for making existing agents compatible with new interface.

This module provides adapters to make our existing agent implementations
work with the new agent interface, preparing for future CrewAI integration.
"""

from typing import Dict, Any, Optional, Type
from datetime import datetime

from core.agents.base.agent_interface import (
    IAgent,
    AgentTask,
    AgentResult,
    AgentContext,
    AgentException
)
from core.agents.base.base_agent import BaseAgent, AgentRequest, AgentResponse
from core.agents.config.agent_config import PriorityLevel
from core.utils.logger import get_logger

logger = get_logger(__name__)

class AgentAdapter(IAgent):
    """Adapter to make existing agents work with new interface"""

    def __init__(self, agent_class: Type[BaseAgent], config: Optional[Dict[str, Any]] = None):
        self.agent_class = agent_class
        self.config = config or {}
        self.agent: Optional[BaseAgent] = None
        self.capabilities: Dict[str, float] = {}

    async def initialize(self) -> None:
        """Initialize the adapted agent"""
        try:
            self.agent = self.agent_class()
            await self.agent.initialize()
            
            # Initialize capabilities based on agent type
            self.capabilities = await self._discover_capabilities()
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise AgentException(f"Agent initialization failed: {str(e)}")

    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process task using adapted agent"""
        if not self.agent:
            raise AgentException("Agent not initialized")

        try:
            # Convert task to agent request
            request = await self._convert_task_to_request(task)
            
            # Process with existing agent
            response = await self.agent.process(request)
            
            # Convert response to agent result
            return await self._convert_response_to_result(response, task)
            
        except Exception as e:
            logger.error(f"Task processing failed: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                status="error",
                error=str(e),
                processing_time=0.0
            )

    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if agent can handle the task"""
        if not task.required_capabilities:
            return True
            
        return all(
            capability in self.capabilities
            for capability in task.required_capabilities
        )

    async def get_capabilities(self) -> list[str]:
        """Get list of agent capabilities"""
        return list(self.capabilities.keys())

    async def health_check(self) -> bool:
        """Check agent health"""
        if not self.agent:
            return False
        return await self.agent.health_check()

    async def _discover_capabilities(self) -> Dict[str, float]:
        """Discover agent capabilities based on type"""
        if isinstance(self.agent, BaseAgent):
            # Map agent methods to capabilities
            capabilities = {}
            
            # Analyze agent methods
            for method_name in dir(self.agent):
                if method_name.startswith('_') or not callable(getattr(self.agent, method_name)):
                    continue
                    
                # Convert method names to capabilities
                capability = method_name.replace('_', '.')
                capabilities[capability] = 1.0  # Default score
                
            return capabilities
            
        return {}

    async def _convert_task_to_request(self, task: AgentTask) -> AgentRequest:
        """Convert task to agent request"""
        # Map priority levels
        priority_map = {
            "high": PriorityLevel.HIGH,
            "medium": PriorityLevel.MEDIUM,
            "low": PriorityLevel.LOW
        }
        
        return AgentRequest(
            request_id=task.task_id,
            user_id=task.context.user_id if task.context else "system",
            priority=priority_map.get(task.priority, PriorityLevel.MEDIUM),
            payload=task.payload,
            timestamp=task.context.timestamp if task.context else datetime.utcnow(),
            context=task.context.metadata if task.context else None
        )

    async def _convert_response_to_result(
        self,
        response: AgentResponse,
        original_task: AgentTask
    ) -> AgentResult:
        """Convert agent response to result"""
        return AgentResult(
            task_id=original_task.task_id,
            status=response.status,
            result=response.data,
            error=response.error,
            processing_time=response.processing_time,
            metadata={
                "cache_hit": response.cache_hit,
                "agent_type": self.agent.__class__.__name__
            }
        )

class AgentFactory(IAgentFactory):
    """Factory for creating agents with appropriate adapters"""

    async def create_agent(
        self,
        agent_type: str,
        use_crew: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> IAgent:
        """Create an agent of specified type"""
        if use_crew:
            # Placeholder for future CrewAI integration
            raise NotImplementedError("CrewAI integration not implemented yet")
            
        # Get agent class based on type
        agent_class = self._get_agent_class(agent_type)
        
        # Create adapter
        adapter = AgentAdapter(agent_class, config)
        await adapter.initialize()
        
        return adapter

    def _get_agent_class(self, agent_type: str) -> Type[BaseAgent]:
        """Get agent class based on type"""
        from core.agents.core.goal_agent import GoalAgent
        from core.agents.core.market_agent import MarketAgent
        
        agent_classes = {
            "goal": GoalAgent,
            "market": MarketAgent
        }
        
        if agent_type not in agent_classes:
            raise AgentException(f"Unknown agent type: {agent_type}")
            
        return agent_classes[agent_type] 