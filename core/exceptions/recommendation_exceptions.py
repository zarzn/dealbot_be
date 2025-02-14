"""Recommendation exceptions module."""

from .base_exceptions import BaseError, NotFoundError, ValidationError

class RecommendationError(BaseError):
    """Base exception for recommendation-related errors."""
    pass

class RecommendationNotFoundError(NotFoundError):
    """Exception raised when a recommendation is not found."""
    pass

class RecommendationValidationError(ValidationError):
    """Exception raised when recommendation data validation fails."""
    pass

class RecommendationProcessingError(RecommendationError):
    """Exception raised when recommendation processing fails."""
    pass

class RecommendationGenerationError(RecommendationError):
    """Exception raised when recommendation generation fails."""
    pass

class RecommendationScoringError(RecommendationError):
    """Exception raised when recommendation scoring fails."""
    pass

class RecommendationFilterError(RecommendationError):
    """Exception raised when recommendation filtering fails."""
    pass

class RecommendationRankingError(RecommendationError):
    """Exception raised when recommendation ranking fails."""
    pass

class RecommendationStorageError(RecommendationError):
    """Exception raised when recommendation storage fails."""
    pass

class RecommendationRetrievalError(RecommendationError):
    """Exception raised when recommendation retrieval fails."""
    pass

__all__ = [
    'RecommendationError',
    'RecommendationNotFoundError',
    'RecommendationValidationError',
    'RecommendationProcessingError',
    'RecommendationGenerationError',
    'RecommendationScoringError',
    'RecommendationFilterError',
    'RecommendationRankingError',
    'RecommendationStorageError',
    'RecommendationRetrievalError'
] 