"""Error handling middleware for the application."""

from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import uuid
import logging

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
    ServiceError,
    NotificationError
)

# Import specific exception types from their modules
# We'll catch these with the generic BaseError handler instead of adding explicit handlers for each type
# from core.exceptions.token_exceptions import TokenError
# from core.exceptions.wallet_exceptions import WalletError
# from core.exceptions.auth_exceptions import TokenError as AuthTokenError
# from core.exceptions.deal_exceptions import DealError
# from core.exceptions.goal_exceptions import GoalError
# from core.exceptions.user_exceptions import UserError
# from core.exceptions.api_exceptions import APIError
# from core.exceptions.analytics_exceptions import AnalyticsError
# from core.exceptions.crawler_exceptions import CrawlerError
# from core.exceptions.data_exceptions import DataError
# from core.exceptions.market_exceptions import MarketError

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
            # Send notification for critical service errors
            await self._send_error_notification(request, e, "ServiceError")
            return JSONResponse(
                status_code=e.status_code or 500,
                content=e.to_dict()
            )
            
        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            # Send notification for database errors
            await self._send_error_notification(request, e, "DatabaseError")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {str(e)}")
            await self._send_error_notification(request, e, "ConfigurationError")
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
            await self._send_error_notification(request, e, "PricePredictionError")
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
            await self._send_error_notification(request, e, "ModelError")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except DealScoreError as e:
            logger.error(f"Deal scoring error: {str(e)}")
            await self._send_error_notification(request, e, "DealScoreError")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except NotificationError as e:
            logger.error(f"Notification error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except BaseError as e:
            logger.error(f"Unexpected base error: {str(e)}")
            await self._send_error_notification(request, e, "BaseError")
            return JSONResponse(
                status_code=500,
                content=e.to_dict()
            )
            
        except Exception as e:
            logger.exception("Unhandled exception")
            await self._send_error_notification(request, e, "UnhandledException")
            return JSONResponse(
                status_code=500,
                content={
                    'error': 'InternalServerError',
                    'message': 'An unexpected error occurred',
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
    async def _send_error_notification(self, request: Request, exception: Exception, error_type: str):
        """Send notification for critical API errors.
        
        Args:
            request: The request that caused the error
            exception: The exception that was raised
            error_type: The type of error that occurred
        """
        try:
            # Import here to avoid circular imports
            from core.notifications import TemplatedNotificationService
            from core.database import get_db, get_async_db_context
            from core.services.auth import get_current_user
            from core.models.enums import NotificationPriority
            
            # Generate a unique error ID for tracking
            error_id = str(uuid.uuid4())
            
            # Extract request information
            url = str(request.url)
            method = request.method
            headers = dict(request.headers)
            # Remove sensitive headers
            if 'authorization' in headers:
                headers['authorization'] = '***REDACTED***'
            if 'cookie' in headers:
                headers['cookie'] = '***REDACTED***'
                
            # Get current user if available
            user_id = None
            try:
                user = await get_current_user(request)
                if user:
                    user_id = user.id
            except Exception:
                # If we can't get the user, continue without user context
                pass
                
            # Prepare error context
            error_context = {
                "error_id": error_id,
                "error_type": error_type,
                "message": str(exception),
                "url": url,
                "method": method,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id) if user_id else "Anonymous"
            }
            
            # Log the full error context for debugging
            logger.error(f"API Error: {error_id}", extra=error_context)
            
            # Get database session using the context manager
            async with get_async_db_context() as db:
                # Initialize notification service
                notification_service = TemplatedNotificationService(db)
                
                # Only send to system admin - in production, you would get admin users from the database
                # For now, we'll send to a predefined admin user ID if available
                from core.config import settings
                admin_user_id = getattr(settings, 'ADMIN_USER_ID', None)
                
                if admin_user_id:
                    # Send notification to admin
                    await notification_service.send_notification(
                        template_id="api_error",
                        user_id=admin_user_id,
                        template_params={
                            "error_type": error_type,
                            "error_message": str(exception),
                            "endpoint": url,
                            "method": method,
                            "error_id": error_id
                        },
                        override_priority=NotificationPriority.HIGH,
                        metadata=error_context,
                        action_url="/admin/errors"
                    )
                    
                    logger.info(f"Sent API error notification to admin: {error_id}")
                
        except Exception as notification_error:
            # Log but don't re-raise to prevent cascading errors
            logger.error(f"Failed to send error notification: {str(notification_error)}") 