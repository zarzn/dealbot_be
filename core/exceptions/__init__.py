"""Core exceptions initialization."""

# Import base exceptions first since they're used by other modules
from .base_exceptions import (
    BaseError,
    ValidationError,
    NotFoundError,
    NotFoundException,  # Alias for backward compatibility
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    ServiceError,
    ExternalServiceError,
    ConfigurationError,
    CacheError,
    IntegrationError,
    NetworkError,
    RateLimitError,
    RateLimitExceededError,
    RepositoryError
)

# Import repository exceptions
from .repository_exceptions import (
    EntityNotFoundError,
    DuplicateEntityError,
    InvalidOperationError,
    RelationshipError,
    ConstraintViolationError,
    TransactionError
)

# Import cache exceptions
from .cache_exceptions import (
    CacheOperationError,
    CacheConnectionError,
    CacheKeyError,
    CacheTimeoutError,
    CacheCapacityError
)

# Import chat exceptions
from .chat_exceptions import (
    ChatError,
    ChatMessageError,
    ChatProcessingError,
    ChatValidationError,
    ChatRateLimitError,
    ChatContextError,
    ChatStorageError,
    ChatRetrievalError,
    ChatTokenLimitError,
    ChatServiceError,
    ChatAuthenticationError,
    ChatAuthorizationError,
    ChatConfigurationError,
    ChatIntegrationError,
    ChatTimeoutError
)

# Import deal exceptions
from .deal_exceptions import (
    DealError,
    DealNotFoundError,
    InvalidDealDataError,
    DealExpirationError,
    DealPriceError,
    DealValidationError,
    DealProcessingError,
    DealScoreError,
    DealAnalysisError,
    DealMatchError
)

# Import market exceptions
from .market_exceptions import (
    MarketError,
    MarketValidationError,
    MarketNotFoundError,
    MarketConnectionError,
    MarketRateLimitError,
    MarketConfigurationError,
    MarketOperationError,
    MarketAuthenticationError,
    MarketProductError,
    ProductNotFoundError,
    PricePredictionError,
    InvalidMarketDataError,
    MarketIntegrationError
)

# Import notification exceptions
from .notification_exceptions import (
    NotificationError,
    NotificationDeliveryError,
    NotificationNotFoundError,
    NotificationRateLimitError,
    InvalidNotificationTemplateError,
    NotificationConfigurationError,
    NotificationChannelError
)

# Import token exceptions
from .token_exceptions import (
    TokenError,
    TokenNotFoundError,
    TokenServiceError,
    TokenBalanceError,
    InvalidBalanceChangeError,
    InsufficientBalanceError,
    InsufficientTokensError,
    InvalidTransactionError,
    WalletConnectionError,
    WalletNotFoundError,
    TransactionNotFoundError,
    TokenPriceError,
    TokenNetworkError,
    InvalidTokenAmountError,
    TokenOperationError,
    TokenAuthorizationError,
    TokenValidationError,
    TokenTransactionError,
    TokenRateLimitError,
    TokenPricingError,
    InvalidPricingError,
    SmartContractError
)

# Import wallet exceptions
from .wallet_exceptions import (
    WalletError,
    WalletNotFoundError,
    WalletConnectionError,
    WalletValidationError,
    WalletAlreadyConnectedError,
    WalletOperationError
)

# Import data exceptions
from .data_exceptions import (
    DataError,
    DataProcessingError,
    DataValidationError,
    DataTransformationError,
    DataIntegrityError,
    DataSyncError,
    DataQualityError
)

# Import user exceptions
from .user_exceptions import (
    UserError,
    UserNotFoundError,
    UserValidationError,
    DuplicateUserError,
    InvalidUserDataError
)

# Import goal exceptions
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
    DealMatchError,
    GoalProcessingError
)

# Import API exceptions
from .api_exceptions import (
    APIError,
    APIRequestError,
    APIRateLimitError,
    APIAuthenticationError,
    APITimeoutError,
    APIResponseValidationError,
    APIServiceUnavailableError,
    AIServiceError,
    RedisCacheError
)

# Import analytics exceptions
from .analytics_exceptions import (
    AnalyticsError,
    AnalyticsProcessingError,
    AnalyticsDataError,
    AnalyticsValidationError
)

# Import crawler exceptions
from .crawler_exceptions import (
    CrawlerError,
    CrawlerRequestError,
    CrawlerParsingError,
    CrawlerRateLimitError,
    CrawlerBlockedError,
    InvalidCrawlerConfigError
)

# Import auth exceptions
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
    TokenRefreshError,
    AccountLockedError,
    EmailNotVerifiedError
)

# Import agent exceptions
from .agent_exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentValidationError,
    AgentCreationError,
    AgentUpdateError,
    AgentDeletionError,
    AgentStatusError,
    AgentProcessingError,
    AgentCommunicationError,
    AgentTimeoutError,
    AgentMemoryError,
    AgentDecisionError,
    AgentCoordinationError
)

# Import recommendation exceptions
from .recommendation_exceptions import (
    RecommendationError,
    RecommendationNotFoundError,
    RecommendationValidationError,
    RecommendationProcessingError,
    RecommendationGenerationError,
    RecommendationScoringError,
    RecommendationFilterError,
    RecommendationRankingError,
    RecommendationStorageError,
    RecommendationRetrievalError
)

# New exceptions
class PriceTrackingError(BaseError):
    """Price tracking error."""
    pass

class WebSocketError(BaseError):
    """WebSocket error."""
    pass

class AgentInitializationError(BaseError):
    """Raised when agent initialization fails."""
    pass

class LLMProviderError(BaseError):
    """Raised when there is an error with the LLM provider."""
    pass

class MarketIntegrationError(BaseError):
    """Raised when there is an error with market integration."""
    pass

class ProcessingError(BaseError):
    """Raised when processing fails."""
    pass

class ResourceNotFoundError(BaseError):
    """Raised when a resource is not found."""
    pass

class ResourceExistsError(BaseError):
    """Raised when a resource already exists."""
    pass

class ServiceUnavailableError(BaseError):
    """Raised when a service is unavailable."""
    pass

class ThirdPartyError(BaseError):
    """Raised when there is an error with a third party service."""
    pass

class TokenError(BaseError):
    """Raised when there is an error with tokens."""
    pass

class UserError(BaseError):
    """Raised when there is a user-related error."""
    pass

__all__ = [
    # Base exceptions
    'BaseError',
    'ValidationError',
    'NotFoundError',
    'NotFoundException',
    'AuthenticationError',
    'AuthorizationError',
    'DatabaseError',
    'ServiceError',
    'ExternalServiceError',
    'ConfigurationError',
    'CacheError',
    'IntegrationError',
    'NetworkError',
    'RateLimitError',
    'RateLimitExceededError',
    'RepositoryError',
    'AccountLockedError',
    'EmailNotVerifiedError',

    # Repository exceptions
    'EntityNotFoundError',
    'DuplicateEntityError',
    'InvalidOperationError',
    'RelationshipError',
    'ConstraintViolationError',
    'TransactionError',

    # Cache exceptions
    'CacheOperationError',
    'CacheConnectionError',
    'CacheKeyError',
    'CacheTimeoutError',
    'CacheCapacityError',

    # Chat exceptions
    'ChatError',
    'ChatMessageError',
    'ChatProcessingError',
    'ChatValidationError',
    'ChatRateLimitError',
    'ChatContextError',
    'ChatStorageError',
    'ChatRetrievalError',
    'ChatTokenLimitError',
    'ChatServiceError',
    'ChatAuthenticationError',
    'ChatAuthorizationError',
    'ChatConfigurationError',
    'ChatIntegrationError',
    'ChatTimeoutError',

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
    'DealMatchError',

    # Market exceptions
    'MarketError',
    'MarketValidationError',
    'MarketNotFoundError',
    'MarketConnectionError',
    'MarketRateLimitError',
    'MarketConfigurationError',
    'MarketOperationError',
    'MarketAuthenticationError',
    'MarketProductError',
    'ProductNotFoundError',
    'PricePredictionError',
    'InvalidMarketDataError',
    'MarketIntegrationError',

    # Notification exceptions
    'NotificationError',
    'NotificationDeliveryError',
    'NotificationNotFoundError',
    'NotificationRateLimitError',
    'InvalidNotificationTemplateError',
    'NotificationConfigurationError',
    'NotificationChannelError',

    # Token exceptions
    'TokenError',
    'TokenNotFoundError',
    'TokenServiceError',
    'TokenBalanceError',
    'InvalidBalanceChangeError',
    'InsufficientBalanceError',
    'InsufficientTokensError',
    'InvalidTransactionError',
    'WalletConnectionError',
    'WalletNotFoundError',
    'TransactionNotFoundError',
    'TokenPriceError',
    'TokenNetworkError',
    'InvalidTokenAmountError',
    'TokenOperationError',
    'TokenAuthorizationError',
    'TokenValidationError',
    'TokenTransactionError',
    'TokenRateLimitError',
    'TokenPricingError',
    'InvalidPricingError',
    'SmartContractError',

    # Wallet exceptions
    'WalletError',
    'WalletNotFoundError',
    'WalletConnectionError',
    'WalletValidationError',
    'WalletAlreadyConnectedError',
    'WalletOperationError',

    # Data exceptions
    'DataError',
    'DataProcessingError',
    'DataValidationError',
    'DataTransformationError',
    'DataIntegrityError',
    'DataSyncError',
    'DataQualityError',

    # User exceptions
    'UserError',
    'UserNotFoundError',
    'UserValidationError',
    'DuplicateUserError',
    'InvalidUserDataError',

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
    'GoalProcessingError',

    # API exceptions
    'APIError',
    'APIRequestError',
    'APIRateLimitError',
    'APIAuthenticationError',
    'APITimeoutError',
    'APIResponseValidationError',
    'APIServiceUnavailableError',
    'AIServiceError',
    'RedisCacheError',

    # Analytics exceptions
    'AnalyticsError',
    'AnalyticsProcessingError',
    'AnalyticsDataError',
    'AnalyticsValidationError',

    # Crawler exceptions
    'CrawlerError',
    'CrawlerRequestError',
    'CrawlerParsingError',
    'CrawlerRateLimitError',
    'CrawlerBlockedError',
    'InvalidCrawlerConfigError',

    # Auth exceptions
    'AuthError',
    'AuthenticationError',
    'AuthorizationError',
    'InvalidCredentialsError',
    'TokenError',
    'SessionExpiredError',
    'PermissionDeniedError',
    'TwoFactorRequiredError',
    'InvalidTwoFactorCodeError',
    'TokenRefreshError',
    'AccountLockedError',
    'EmailNotVerifiedError',

    # Agent exceptions
    'AgentError',
    'AgentNotFoundError',
    'AgentValidationError',
    'AgentCreationError',
    'AgentUpdateError',
    'AgentDeletionError',
    'AgentStatusError',
    'AgentProcessingError',
    'AgentCommunicationError',
    'AgentTimeoutError',
    'AgentMemoryError',
    'AgentDecisionError',
    'AgentCoordinationError',

    # Recommendation exceptions
    'RecommendationError',
    'RecommendationNotFoundError',
    'RecommendationValidationError',
    'RecommendationProcessingError',
    'RecommendationGenerationError',
    'RecommendationScoringError',
    'RecommendationFilterError',
    'RecommendationRankingError',
    'RecommendationStorageError',
    'RecommendationRetrievalError',

    # New exceptions
    'PriceTrackingError',
    'WebSocketError',
    'AgentInitializationError',
    'LLMProviderError',
    'MarketIntegrationError',
    'ProcessingError',
    'ResourceNotFoundError',
    'ResourceExistsError',
    'ServiceUnavailableError',
    'ThirdPartyError',
    'UserError'
]
