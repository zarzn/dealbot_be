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
