"""Common schema models."""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ResponseStatus(str, Enum):
    """Response status enum."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class StatusResponse(BaseModel):
    """Standard status response model."""
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: str
    data: Optional[Dict[str, Any]] = None 