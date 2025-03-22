"""JSON utilities for handling complex types.

This module provides utilities for working with JSON serialization,
especially for complex types like datetime and UUID objects.
"""

import json
import logging
from datetime import datetime
from uuid import UUID
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects and other special types."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        # Handle pydantic HttpUrl
        elif hasattr(obj, '__str__') and (hasattr(obj, 'host') or hasattr(obj, 'scheme')):
            return str(obj)
        # Handle any other objects with __dict__
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

def sanitize_for_json(data: Any) -> Any:
    """Recursively sanitize data to ensure it's JSON serializable.
    
    This function traverses complex data structures like dictionaries and lists,
    converting non-JSON-serializable objects to string representations.
    
    Args:
        data: The data to sanitize
        
    Returns:
        The sanitized data, ready for JSON serialization
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime, UUID)):
        return str(data)
    elif hasattr(data, '__str__') and (hasattr(data, 'host') or hasattr(data, 'scheme')):
        # Handle URL objects
        return str(data)
    elif isinstance(data, (str, int, float, bool, type(None))):
        # These types are already JSON serializable
        return data
    else:
        # Convert any other type to string
        try:
            return str(data)
        except Exception as e:
            logger.error(f"Error converting object to string: {str(e)}")
            return "UNSERIALIZABLE_OBJECT"

def json_dumps(data: Any) -> str:
    """Safely convert data to JSON string with special type handling.
    
    Args:
        data: The data to convert to JSON
        
    Returns:
        A JSON string representation
        
    Raises:
        TypeError: If the data cannot be serialized even after sanitization
    """
    try:
        # First try with the custom encoder
        return json.dumps(data, cls=DateTimeEncoder)
    except TypeError:
        # If that fails, try sanitizing the data first
        sanitized_data = sanitize_for_json(data)
        return json.dumps(sanitized_data)

def json_loads(json_str: str) -> Any:
    """Safely parse JSON string.
    
    Args:
        json_str: The JSON string to parse
        
    Returns:
        The parsed data
        
    Raises:
        ValueError: If the string is not valid JSON
    """
    return json.loads(json_str) 