"""Error handling middleware for the application."""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.exceptions.base_exceptions import (
    BaseError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    DatabaseError,
    CacheError,
    ExternalServiceError,
    ConfigurationError,
    TokenError,
    WalletError,
    AgentError,
    DealError,
    GoalError,
    UserError,
    APIError,
    AnalyticsError,
    CrawlerError,
    DataError,
    PriceError,
    NotificationError,
    MarketError
)
from core.exceptions.price import (
    PriceTrackingError,
    PricePredictionError,
    InsufficientDataError,
    ModelError,
    DealScoreError
)
from core.utils.logger import get_logger

logger = get_logger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling custom exceptions."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request and handle any exceptions."""
        try:
            return await call_next(request)
            
        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            return JSONResponse(
                status_code=400,
                content=e.to_dict()
            )
            
        except NotFoundError as e:
            logger.info(f"Resource not found: {str(e)}")
            return JSONResponse(
                status_code=404,
                content=e.to_dict()
            )
            
        except AuthenticationError as e:
            logger.warning(f"Authentication error: {str(e)}")
            return JSONResponse(
                status_code=401,
                content=e.to_dict()
            )
            
        except AuthorizationError as e:
            logger.warning(f"Authorization error: {str(e)}")
            return JSONResponse(
                status_code=403,
                content=e.to_dict()
            )
            
        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}")
            return JSONResponse(
                status_code=429,
                content=e.to_dict(),
                headers={"Retry-After": str(int((e.reset_at - e.timestamp).total_seconds()))}
            )
            
        except ServiceError as e:
            logger.error(f"Service error: {str(e)}")
            return JSONResponse(
                status_code=e.status_code or 500,
                content=e.to_dict()
            )
            
        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except CacheError as e:
            logger.error(f"Cache error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except PriceTrackingError as e:
            logger.error(f"Price tracking error: {str(e)}")
            return JSONResponse(
                status_code=400,
                content=e.to_dict()
            )
            
        except PricePredictionError as e:
            logger.error(f"Price prediction error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except InsufficientDataError as e:
            logger.warning(f"Insufficient data: {str(e)}")
            return JSONResponse(
                status_code=400,
                content=e.to_dict()
            )
            
        except ModelError as e:
            logger.error(f"Model error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except DealScoreError as e:
            logger.error(f"Deal scoring error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except BaseError as e:
            logger.error(f"Unexpected base error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except Exception as e:
            logger.exception("Unhandled exception")
            return JSONResponse(
                status_code=500,
                content={
                    'error': 'InternalServerError',
                    'message': 'An unexpected error occurred',
                    'timestamp': datetime.utcnow().isoformat()
                }
            ) 