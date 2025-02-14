"""Repository-related exceptions."""

from typing import Dict, Any, Optional
from .base_exceptions import BaseError


class RepositoryError(BaseError):
    """Base exception for repository-related errors."""
    
    def __init__(
        self,
        message: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            **self.details
        }


class EntityNotFoundError(RepositoryError):
    """Raised when an entity is not found in the repository."""
    
    def __init__(
        self,
        message: str,
        entity_type: str,
        entity_id: Any,
        operation: str = 'find'
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'entity_type': entity_type,
                'entity_id': entity_id
            }
        )


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""
    
    def __init__(
        self,
        message: str,
        entity_type: str,
        unique_fields: Dict[str, Any],
        operation: str = 'create'
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'entity_type': entity_type,
                'unique_fields': unique_fields
            }
        )


class InvalidOperationError(RepositoryError):
    """Raised when an invalid operation is attempted on an entity."""
    
    def __init__(
        self,
        message: str,
        entity_type: str,
        operation: str,
        reason: str
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'entity_type': entity_type,
                'reason': reason
            }
        )


class RelationshipError(RepositoryError):
    """Raised when there are issues with entity relationships."""
    
    def __init__(
        self,
        message: str,
        entity_type: str,
        related_type: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'entity_type': entity_type,
                'related_type': related_type,
                **(details or {})
            }
        )


class ConstraintViolationError(RepositoryError):
    """Raised when a database constraint is violated."""
    
    def __init__(
        self,
        message: str,
        entity_type: str,
        constraint_name: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'entity_type': entity_type,
                'constraint_name': constraint_name,
                **(details or {})
            }
        )


class TransactionError(RepositoryError):
    """Raised when there are issues with database transactions."""
    
    def __init__(
        self,
        message: str,
        operation: str,
        transaction_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            operation=operation,
            details={
                'transaction_id': transaction_id,
                **(details or {})
            }
        ) 