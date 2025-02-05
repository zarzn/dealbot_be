"""Agent-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base import BaseError, ValidationError

class AgentError(BaseError):
    """Base class for agent-related errors."""
    
    def __init__(
        self,
        message: str = "Agent operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="agent_error",
            details=details
        )

class AgentNotFoundError(AgentError):
    """Raised when an agent cannot be found."""
    
    def __init__(
        self,
        agent_id: str,
        message: str = "Agent not found"
    ):
        super().__init__(
            message=message,
            details={"agent_id": agent_id}
        )

class AgentCommunicationError(AgentError):
    """Raised when there's a communication error between agents."""
    
    def __init__(
        self,
        source_agent: str,
        target_agent: str,
        message: str = "Agent communication failed"
    ):
        super().__init__(
            message=message,
            details={
                "source_agent": source_agent,
                "target_agent": target_agent
            }
        )

class AgentTimeoutError(AgentError):
    """Raised when an agent operation times out."""
    
    def __init__(
        self,
        agent_id: str,
        operation: str,
        timeout: float,
        message: str = "Agent operation timed out"
    ):
        super().__init__(
            message=message,
            details={
                "agent_id": agent_id,
                "operation": operation,
                "timeout": timeout
            }
        )

class AgentMemoryError(AgentError):
    """Raised when an agent exceeds memory limits."""
    
    def __init__(
        self,
        agent_id: str,
        current_usage: int,
        limit: int,
        message: str = "Agent memory limit exceeded"
    ):
        super().__init__(
            message=message,
            details={
                "agent_id": agent_id,
                "current_usage": current_usage,
                "limit": limit
            }
        )

class AgentDecisionError(AgentError):
    """Raised when an agent fails to make a decision."""
    
    def __init__(
        self,
        agent_id: str,
        context: Dict[str, Any],
        message: str = "Agent decision failed"
    ):
        super().__init__(
            message=message,
            details={
                "agent_id": agent_id,
                "context": context
            }
        )

__all__ = [
    'AgentError',
    'AgentNotFoundError',
    'AgentCommunicationError',
    'AgentTimeoutError',
    'AgentMemoryError',
    'AgentDecisionError'
] 