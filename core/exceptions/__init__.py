"""Core exceptions initialization."""

# Re-export base exceptions
from .base import (
    BaseError,
    ValidationError,
    NotFoundException,
    NotFoundError,
    DatabaseError,
    RepositoryError,
    NetworkError,
    ServiceError,
    ExternalServiceError,
    RateLimitError,
    RateLimitExceededError,
    IntegrationError
)

# Re-export deal exceptions
from .deal_exceptions import (
    DealError,
    DealNotFoundError,
    InvalidDealDataError,
    DealExpirationError,
    DealPriceError,
    DealValidationError,
    DealProcessingError,
    DealScoreError,
    DealAnalysisError
)

# Re-export data exceptions
from .data_exceptions import (
    DataError,
    DataProcessingError,
    DataValidationError,
    DataTransformationError,
    DataIntegrityError,
    DataSyncError,
    DataQualityError
)

# Re-export user exceptions
from .user_exceptions import (
    UserError,
    UserNotFoundError,
    DuplicateUserError,
    InvalidUserDataError,
    UserValidationError
)

# Re-export token exceptions
from .token_exceptions import (
    TokenError,
    TokenBalanceError,
    TokenTransactionError,
    TokenValidationError,
    TokenRateLimitError,
    InsufficientBalanceError,
    InsufficientTokensError,
    SmartContractError,
    InvalidBalanceChangeError,
    TokenPricingError,
    InvalidPricingError,
    TokenNetworkError,
    TokenOperationError,
    TokenServiceError,
    TokenNotFoundError
)

# Re-export wallet exceptions
from .wallet_exceptions import (
    WalletError,
    WalletNotFoundError,
    WalletConnectionError,
    WalletValidationError,
    WalletAlreadyConnectedError,
    WalletOperationError
)

# Re-export goal exceptions
from .goal_exceptions import (
    GoalError,
    GoalValidationError,
    GoalNotFoundError,
    InvalidGoalDataError,
    GoalConstraintError,
    GoalLimitExceededError,
    GoalStatusError,
    GoalCreationError,
    GoalUpdateError,
    InvalidGoalConstraintsError,
    DealMatchError
)

# Re-export agent exceptions
from .agent_exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentCommunicationError,
    AgentTimeoutError,
    AgentMemoryError,
    AgentDecisionError
)

# Re-export notification exceptions
from .notification_exceptions import (
    NotificationError,
    NotificationNotFoundError,
    NotificationDeliveryError,
    NotificationRateLimitError,
    InvalidNotificationTemplateError
)

# Re-export crawler exceptions
from .crawler_exceptions import (
    CrawlerError,
    CrawlerRequestError,
    CrawlerParsingError,
    CrawlerRateLimitError,
    CrawlerBlockedError,
    InvalidCrawlerConfigError
)

# Re-export auth exceptions
from .auth_exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    TokenError,
    SessionExpiredError,
    PermissionDeniedError,
    TwoFactorRequiredError,
    InvalidTwoFactorCodeError,
    AuthenticationError,
    AuthorizationError
)

# Re-export API exceptions
from .api_exceptions import (
    APIError,
    APIRequestError,
    APIRateLimitError,
    APIAuthenticationError,
    APITimeoutError,
    APIResponseValidationError,
    APIServiceUnavailableError,
    AIServiceError
)

# Re-export market exceptions
from .market_exceptions import (
    MarketError,
    MarketValidationError,
    InvalidMarketDataError,
    MarketNotFoundError,
    MarketConnectionError,
    MarketRateLimitError,
    MarketConfigurationError,
    MarketOperationError,
    MarketAuthenticationError,
    InvalidDealDataError
)

# Re-export analytics exceptions
from .analytics_exceptions import (
    AnalyticsError,
    AnalyticsProcessingError,
    AnalyticsDataError,
    AnalyticsValidationError
)

# Re-export cache exceptions
from .cache_exceptions import (
    CacheError,
    CacheOperationError,
    CacheConnectionError,
    CacheKeyError,
    CacheTimeoutError,
    CacheCapacityError
)

# Define what's available when importing from core.exceptions
__all__ = [
    # Base exceptions
    'BaseError',
    'ValidationError',
    'NotFoundException',
    'NotFoundError',
    'DatabaseError',
    'RepositoryError',
    'NetworkError',
    'ServiceError',
    'ExternalServiceError',
    'RateLimitError',
    'RateLimitExceededError',
    'IntegrationError',
    
    # Market exceptions
    'MarketError',
    'MarketValidationError',
    'InvalidMarketDataError',
    'MarketNotFoundError',
    'MarketConnectionError',
    'MarketRateLimitError',
    'MarketConfigurationError',
    'MarketOperationError',
    'MarketAuthenticationError',
    'InvalidDealDataError',
    
    # Deal exceptions
    'DealError',
    'DealNotFoundError',
    'InvalidDealDataError',
    'DealExpirationError',
    'DealPriceError',
    'DealValidationError',
    'DealProcessingError',
    'DealScoreError',
    'DealAnalysisError',
    
    # User exceptions
    'UserError',
    'UserNotFoundError',
    'DuplicateUserError',
    'InvalidUserDataError',
    'UserValidationError',
    
    # Token exceptions
    'TokenError',
    'TokenBalanceError',
    'TokenTransactionError',
    'TokenValidationError',
    'TokenRateLimitError',
    'InsufficientBalanceError',
    'InsufficientTokensError',
    'SmartContractError',
    'InvalidBalanceChangeError',
    'TokenPricingError',
    'InvalidPricingError',
    'TokenNetworkError',
    'TokenOperationError',
    'TokenServiceError',
    'TokenNotFoundError',
    
    # Wallet exceptions
    'WalletError',
    'WalletNotFoundError',
    'WalletConnectionError',
    'WalletValidationError',
    'WalletAlreadyConnectedError',
    'WalletOperationError',
    
    # Goal exceptions
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
    
    # Agent exceptions
    'AgentError',
    'AgentNotFoundError',
    'AgentCommunicationError',
    'AgentTimeoutError',
    'AgentMemoryError',
    'AgentDecisionError',
    
    # Notification exceptions
    'NotificationError',
    'NotificationNotFoundError',
    'NotificationDeliveryError',
    'NotificationRateLimitError',
    'InvalidNotificationTemplateError',
    
    # Crawler exceptions
    'CrawlerError',
    'CrawlerRequestError',
    'CrawlerParsingError',
    'CrawlerRateLimitError',
    'CrawlerBlockedError',
    'InvalidCrawlerConfigError',
    
    # Auth exceptions
    'AuthError',
    'InvalidCredentialsError',
    'SessionExpiredError',
    'PermissionDeniedError',
    'TwoFactorRequiredError',
    'InvalidTwoFactorCodeError',
    'AuthenticationError',
    'AuthorizationError',
    
    # API exceptions
    'APIError',
    'APIRequestError',
    'APIRateLimitError',
    'APIAuthenticationError',
    'APITimeoutError',
    'APIResponseValidationError',
    'APIServiceUnavailableError',
    'AIServiceError',
    
    # Analytics exceptions
    'AnalyticsError',
    'AnalyticsProcessingError',
    'AnalyticsDataError',
    'AnalyticsValidationError',

    # Cache exceptions
    'CacheError',
    'CacheOperationError',
    'CacheConnectionError',
    'CacheKeyError',
    'CacheTimeoutError',
    'CacheCapacityError',

    # Data exceptions
    'DataError',
    'DataProcessingError',
    'DataValidationError',
    'DataTransformationError',
    'DataIntegrityError',
    'DataSyncError',
    'DataQualityError'
]

# Exceptions module for AI Agentic Deals System

class BaseError(Exception):
    """Base error class for all custom exceptions."""
    pass

# Authentication Exceptions
class AuthError(BaseError):
    """Base class for authentication-related errors."""
    pass

class InvalidCredentialsError(AuthError):
    """Raised when credentials are invalid."""
    pass

class TokenError(AuthError):
    """Base class for token-related errors."""
    pass

class TokenValidationError(TokenError):
    """Raised when token validation fails."""
    pass

class TokenBalanceError(TokenError):
    """Raised when there are token balance issues."""
    pass

class InsufficientBalanceError(TokenBalanceError):
    """Raised when user has insufficient token balance."""
    pass

class TokenTransactionError(TokenError):
    """Raised when token transaction fails."""
    pass

class SmartContractError(TokenError):
    """Raised when smart contract operation fails."""
    pass

# User Exceptions
class UserError(BaseError):
    """Base class for user-related errors."""
    pass

class UserNotFoundError(UserError):
    """Raised when user is not found."""
    def __init__(self, user_id: str):
        self.message = f"User not found: {user_id}"
        super().__init__(self.message)

class UserValidationError(UserError):
    """Raised when user validation fails."""
    pass

# Market Exceptions
class MarketError(BaseError):
    """Base class for market-related errors."""
    pass

class MarketValidationError(MarketError):
    """Raised when market validation fails."""
    pass

class MarketNotFoundError(MarketError):
    """Raised when market is not found."""
    pass

class MarketConnectionError(MarketError):
    """Raised when connection to market fails."""
    pass

class MarketRateLimitError(MarketError):
    """Raised when market rate limit is exceeded."""
    pass

class MarketConfigurationError(MarketError):
    """Raised when market configuration is invalid."""
    pass

class MarketOperationError(MarketError):
    """Raised when market operation fails."""
    pass

# Goal Exceptions
class GoalError(BaseError):
    """Base class for goal-related errors."""
    pass

class GoalNotFoundError(GoalError):
    """Raised when goal is not found."""
    pass

class GoalValidationError(GoalError):
    """Raised when goal validation fails."""
    pass

class GoalConstraintError(GoalError):
    """Raised when goal constraints are invalid."""
    pass

class GoalStatusError(GoalError):
    """Raised when goal status transition is invalid."""
    pass

class GoalCreationError(GoalError):
    """Raised when goal creation fails."""
    pass

class GoalUpdateError(GoalError):
    """Raised when goal update fails."""
    pass

# Notification Exceptions
class NotificationError(BaseError):
    """Base class for notification-related errors."""
    pass

class NotificationDeliveryError(NotificationError):
    """Raised when notification delivery fails."""
    pass

class NotificationNotFoundError(NotificationError):
    """Raised when notification is not found."""
    pass

class NotificationRateLimitError(NotificationError):
    """Raised when notification rate limit is exceeded."""
    pass

class InvalidNotificationTemplateError(NotificationError):
    """Raised when notification template is invalid."""
    pass

# Wallet Exceptions
class WalletError(BaseError):
    """Base class for wallet-related errors."""
    pass

class WalletConnectionError(WalletError):
    """Raised when wallet connection fails."""
    pass

class WalletValidationError(WalletError):
    """Raised when wallet validation fails."""
    pass

# Database Exceptions
class DatabaseError(BaseError):
    """Base class for database-related errors."""
    pass

class ValidationError(BaseError):
    """Base class for validation-related errors."""
    pass

class ServiceError(BaseError):
    """Base class for service-related errors."""
    pass

class InvalidGoalConstraintsError(ValidationError):
    """Raised when goal constraints are invalid."""
    pass
