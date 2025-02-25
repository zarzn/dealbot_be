"""Task-related exceptions."""

from typing import Optional, Dict, Any
from .base_exceptions import BaseError

class TaskError(BaseError):
    """Base exception for task-related errors."""
    def __init__(
        self,
        message: str = "Task operation failed",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code or "task_error",
            details=details
        )

class TaskNotFoundError(TaskError):
    """Exception raised when a task is not found."""
    def __init__(
        self,
        message: str = "Task not found",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="task_not_found",
            details=details
        )

class TaskValidationError(TaskError):
    """Exception raised when task validation fails."""
    def __init__(
        self,
        message: str = "Task validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="task_validation_error",
            details=details
        )

class TaskExecutionError(TaskError):
    """Exception raised when task execution fails."""
    def __init__(
        self,
        message: str = "Task execution failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="task_execution_error",
            details=details
        )

class TaskTimeoutError(TaskError):
    """Exception raised when a task times out."""
    def __init__(
        self,
        message: str = "Task timed out",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="task_timeout",
            details=details
        )

class TaskCancellationError(TaskError):
    """Exception raised when a task is cancelled."""
    def __init__(
        self,
        message: str = "Task was cancelled",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="task_cancelled",
            details=details
        ) 