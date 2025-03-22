"""JSON utility functions.

This module provides utilities for handling JSON serialization of complex data types.
"""

import json
from datetime import datetime
from uuid import UUID
from typing import Any, Dict, List

class EnhancedJSONEncoder(json.JSONEncoder):
    """Enhanced JSON encoder that handles common Python objects.
    
    This encoder properly serializes:
    - datetime objects (to ISO format)
    - UUID objects (to string)
    - URL objects (to string)
    - objects with __dict__ (as dictionary)
    """
    
    def default(self, obj: Any) -> Any:
        """Encode object to JSON-serializable form."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        # Handle pydantic HttpUrl and similar URL types
        elif hasattr(obj, '__str__') and (hasattr(obj, 'host') or hasattr(obj, 'scheme')):
            return str(obj)
        # Handle objects with __dict__ attribute (like many custom classes)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def sanitize_for_json(data: Any) -> Any:
    """Recursively sanitize data to ensure it's JSON serializable.
    
    Args:
        data: The data to sanitize.
        
    Returns:
        JSON-serializable version of the data.
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime, UUID)):
        return str(data)
    elif hasattr(data, '__str__') and (hasattr(data, 'host') or hasattr(data, 'scheme')):
        return str(data)
    elif not isinstance(data, (str, int, float, bool, type(None))):
        return str(data)
    return data


def dumps(obj: Any, **kwargs) -> str:
    """Dump object to JSON string.
    
    Args:
        obj: The object to serialize.
        **kwargs: Additional arguments to pass to json.dumps.
        
    Returns:
        JSON string.
    """
    try:
        return json.dumps(obj, cls=EnhancedJSONEncoder, **kwargs)
    except TypeError:
        # Fallback to sanitizing data first
        sanitized = sanitize_for_json(obj)
        return json.dumps(sanitized, **kwargs)


def loads(s: str, **kwargs) -> Any:
    """Load JSON string to Python object.
    
    Args:
        s: The string to parse.
        **kwargs: Additional arguments to pass to json.loads.
        
    Returns:
        Parsed Python object.
    """
    return json.loads(s, **kwargs) 