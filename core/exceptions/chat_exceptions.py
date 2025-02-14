"""Chat-related exceptions."""

from .base_exceptions import BaseError


class ChatError(BaseError):
    """Base exception for chat-related errors."""


class ChatMessageError(ChatError):
    """Exception raised for errors related to chat messages."""


class ChatProcessingError(ChatError):
    """Exception raised when there's an error processing chat messages."""


class ChatValidationError(ChatError):
    """Exception raised when chat data validation fails."""


class ChatRateLimitError(ChatError):
    """Exception raised when chat rate limits are exceeded."""


class ChatContextError(ChatError):
    """Exception raised when there are issues with chat context management."""


class ChatStorageError(ChatError):
    """Exception raised when there are issues storing chat data."""


class ChatRetrievalError(ChatError):
    """Exception raised when there are issues retrieving chat data."""


class ChatTokenLimitError(ChatError):
    """Exception raised when chat token limits are exceeded."""


class ChatServiceError(ChatError):
    """Exception raised when there are issues with the chat service."""


class ChatAuthenticationError(ChatError):
    """Exception raised when there are chat authentication issues."""


class ChatAuthorizationError(ChatError):
    """Exception raised when there are chat authorization issues."""


class ChatConfigurationError(ChatError):
    """Exception raised when there are chat configuration issues."""


class ChatIntegrationError(ChatError):
    """Exception raised when there are issues with chat integrations."""


class ChatTimeoutError(ChatError):
    """Exception raised when chat operations timeout.""" 