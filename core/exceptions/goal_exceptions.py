"""Goal-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base_exceptions import BaseError, ValidationError

class GoalError(BaseError):
    """Base class for goal-related errors."""
    
    def __init__(
        self,
        message: str = "Goal operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class GoalValidationError(ValidationError):
    """Raised when goal validation fails."""
    
    def __init__(
        self,
        message: str = "Goal validation error",
        errors: Optional[Dict[str, Any]] = None,
        field_prefix: str = "goal"
    ):
        super().__init__(
            message=message,
            errors=errors,
            field_prefix=field_prefix
        )

class GoalNotFoundError(GoalError):
    """Raised when a goal cannot be found."""
    
    def __init__(
        self,
        goal_id: str,
        message: str = "Goal not found"
    ):
        super().__init__(
            message=message,
            details={"goal_id": goal_id}
        )

class InvalidGoalDataError(GoalError):
    """Raised when goal data is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid goal data",
        validation_errors: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            details={"validation_errors": validation_errors or []}
        )

class GoalConstraintError(GoalError):
    """Raised when goal constraints are invalid."""
    
    def __init__(
        self,
        message: str = "Invalid goal constraints",
        constraint_errors: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            details={"constraint_errors": constraint_errors or []}
        )

class GoalLimitExceededError(GoalError):
    """Raised when user exceeds their goal limit."""
    
    def __init__(
        self,
        user_id: str,
        current_count: int,
        max_allowed: int,
        message: str = "Goal limit exceeded"
    ):
        super().__init__(
            message=message,
            details={
                "user_id": user_id,
                "current_count": current_count,
                "max_allowed": max_allowed
            }
        )

class GoalStatusError(GoalError):
    """Raised when an invalid goal status transition is attempted."""
    
    def __init__(
        self,
        goal_id: str,
        current_status: str,
        target_status: str,
        message: str = "Invalid goal status transition"
    ):
        super().__init__(
            message=message,
            details={
                "goal_id": goal_id,
                "current_status": current_status,
                "target_status": target_status
            }
        )

class GoalCreationError(GoalError):
    """Raised when goal creation fails."""
    
    def __init__(
        self,
        message: str = "Failed to create goal",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

class GoalUpdateError(GoalError):
    """Raised when goal update fails."""
    
    def __init__(
        self,
        goal_id: str,
        message: str = "Failed to update goal",
        details: Optional[Dict[str, Any]] = None
    ):
        update_details = {"goal_id": goal_id}
        if details:
            update_details.update(details)
        super().__init__(
            message=message,
            details=update_details
        )

class InvalidGoalConstraintsError(GoalError):
    """Raised when goal constraints are invalid."""
    
    def __init__(
        self,
        message: str = "Invalid goal constraints",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

class DealMatchError(GoalError):
    """Raised when there's an error matching deals to a goal."""
    
    def __init__(
        self,
        goal_id: str,
        message: str = "Error matching deals to goal",
        details: Optional[Dict[str, Any]] = None
    ):
        match_details = {"goal_id": goal_id}
        if details:
            match_details.update(details)
        super().__init__(
            message=message,
            details=match_details
        )

class GoalProcessingError(GoalError):
    """Raised when there's an error processing a goal."""
    
    def __init__(
        self,
        message: str = "Error processing goal",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

__all__ = [
    'GoalError',
    'GoalValidationError',
    'GoalNotFoundError',
    'InvalidGoalDataError',
    'GoalConstraintError',
    'GoalLimitExceededError',
    'GoalStatusError',
    'GoalCreationError',
    'GoalUpdateError',
    'InvalidGoalConstraintsError',
    'DealMatchError',
    'GoalProcessingError'
] 