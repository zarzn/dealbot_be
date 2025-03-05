"""
WebSocket API module for backward compatibility.

This module re-exports the websocket functionality from core.websockets
to maintain backward compatibility with existing code.
"""

# Re-export the connection manager
from core.websockets.connection_manager import get_connection_manager

# Re-export any other necessary components
__all__ = ["get_connection_manager"] 