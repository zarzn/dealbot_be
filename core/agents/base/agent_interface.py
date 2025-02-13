"""Agent interface for supporting multiple agent implementations.

This module defines the core interfaces that all agent implementations must follow,
whether they use our custom implementation or CrewAI.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel
from datetime import datetime

class AgentContext(BaseModel):
    """Context information for agent operations"""
    user_id: str
    session_id: str
    timestamp: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = {}

@runtime_checkable
class AgentCapability(Protocol):
    """Protocol defining what capabilities an agent has"""
    async def can_handle(self, task_type: str) -> bool: ...
    async def get_capability_score(self, task_type: str) -> float: ...

class AgentTask(BaseModel):
    """Model representing a task for an agent"""
    task_id: str
    task_type: str
    priority: str
    payload: Dict[str, Any]
    context: Optional[AgentContext] = None
    required_capabilities: list[str] = []

class AgentResult(BaseModel):
    """Model representing the result of an agent's work"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float
    metadata: Dict[str, Any] = {}

class IAgent(ABC):
    """Core interface that all agent implementations must implement"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize agent resources"""
        pass

    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a task and return result"""
        pass

    @abstractmethod
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if agent can handle the task"""
        pass

    @abstractmethod
    async def get_capabilities(self) -> list[str]:
        """Get list of agent capabilities"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check agent health status"""
        pass

class IAgentFactory(ABC):
    """Factory interface for creating agents"""
    
    @abstractmethod
    async def create_agent(
        self,
        agent_type: str,
        use_crew: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> IAgent:
        """Create an agent of specified type"""
        pass

class IAgentCoordinator(ABC):
    """Interface for agent coordination and orchestration"""
    
    @abstractmethod
    async def assign_task(self, task: AgentTask) -> str:
        """Assign task to most suitable agent"""
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a task"""
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        pass

class AgentException(Exception):
    """Base exception for agent-related errors"""
    pass

class AgentInitializationError(AgentException):
    """Error during agent initialization"""
    pass

class AgentProcessingError(AgentException):
    """Error during task processing"""
    pass

class AgentCapabilityError(AgentException):
    """Error related to agent capabilities"""
    pass

class AgentCoordinationError(AgentException):
    """Error in agent coordination"""
    pass 