"""Agent exceptions module."""

from .base_exceptions import BaseError, NotFoundError, ValidationError

class AgentError(BaseError):
    """Base exception for agent-related errors."""
    pass

class AgentNotFoundError(NotFoundError):
    """Exception raised when an agent is not found."""
    pass

class AgentValidationError(ValidationError):
    """Exception raised when agent data validation fails."""
    pass

class AgentCreationError(AgentError):
    """Exception raised when agent creation fails."""
    pass

class AgentUpdateError(AgentError):
    """Exception raised when agent update fails."""
    pass

class AgentDeletionError(AgentError):
    """Exception raised when agent deletion fails."""
    pass

class AgentStatusError(AgentError):
    """Exception raised when agent status transition is invalid."""
    pass

class AgentProcessingError(AgentError):
    """Exception raised when agent processing fails."""
    pass

class AgentCommunicationError(AgentError):
    """Exception raised when agent communication fails."""
    pass

class AgentTimeoutError(AgentError):
    """Exception raised when agent operation times out."""
    pass

class AgentMemoryError(AgentError):
    """Exception raised when agent memory limit is exceeded."""
    pass

class AgentDecisionError(AgentError):
    """Exception raised when agent decision making fails."""
    pass

class AgentCoordinationError(AgentError):
    """Exception raised when agent coordination fails."""
    pass

class LLMProviderError(AgentError):
    """Exception raised when there is an error with the LLM provider."""
    pass

__all__ = [
    'AgentError',
    'AgentNotFoundError',
    'AgentValidationError',
    'AgentCreationError',
    'AgentUpdateError',
    'AgentDeletionError',
    'AgentStatusError',
    'AgentProcessingError',
    'AgentCommunicationError',
    'AgentTimeoutError',
    'AgentMemoryError',
    'AgentDecisionError',
    'AgentCoordinationError',
    'LLMProviderError'
] 