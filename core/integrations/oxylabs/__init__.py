"""Oxylabs web scraping integration package."""

# New modular client
from core.integrations.oxylabs.client import (
    OxylabsClient,
    get_oxylabs_client,
)

# Backward compatibility exports
from core.integrations.oxylabs.compatibility import (
    OxylabsService,
    get_oxylabs,
)

__all__ = [
    # New modular API
    "OxylabsClient", 
    "get_oxylabs_client",
    
    # Backward compatibility
    "OxylabsService",
    "get_oxylabs",
] 