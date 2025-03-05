"""Agent context module.

This module provides the AgentContext class for agent creation.
"""

from typing import Dict, Any, Optional, List

class AgentContext:
    """Context for agent creation."""
    
    def __init__(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize agent context.
        
        Args:
            user_id: User ID
            session_id: Session ID
            metadata: Additional metadata
        """
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata or {}
        self.conversation_history = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary.
        
        Returns:
            Dictionary representation of context
        """
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "conversation_history": self.conversation_history
        } 