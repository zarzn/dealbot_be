"""JSON encoders for handling complex types.

This module provides encoder classes for JSON serialization of various types.
"""

import json
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import Any

class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID objects.
    
    This encoder converts UUID objects to strings during JSON serialization.
    """
    
    def default(self, obj: Any) -> Any:
        """Convert object to a JSON serializable format.
        
        Args:
            obj: The object to convert
            
        Returns:
            A JSON serializable representation of the object
        """
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj) 