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

class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    version: str
    environment: str
    database_connected: bool
    redis_connected: bool
    uptime: float 