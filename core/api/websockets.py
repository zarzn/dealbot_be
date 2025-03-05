"""WebSocket API module.

This module re-exports the WebSocket functionality from core.websockets
for backward compatibility with tests expecting it at core.api.websockets.
"""

from core.websockets.connection_manager import ConnectionManager, get_connection_manager

__all__ = ["ConnectionManager", "get_connection_manager"] 