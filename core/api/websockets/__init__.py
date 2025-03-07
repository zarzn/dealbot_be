"""WebSocket API module.

This module re-exports the WebSocket functionality from core.websockets
for backward compatibility with tests expecting it at core.api.websockets.
"""

from core.websockets.connection_manager import ConnectionManager, get_connection_manager
from core.websockets.price_updates import PriceUpdateManager, get_price_update_manager

__all__ = [
    "ConnectionManager", 
    "get_connection_manager",
    "PriceUpdateManager",
    "get_price_update_manager"
] 