"""Authentication middleware module."""

import logging
from typing import Optional, Callable, Set

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings
from core.services.auth import AuthService
from core.database import get_async_db_session as get_db
from core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for request authentication."""

    def __init__(
        self,
        app: ASGIApp,
        auth_service: Optional[AuthService] = None,
        exclude_paths: Set[str] = settings.AUTH_EXCLUDE_PATHS
    ):
        super().__init__(app)
        # If auth_service is not provided, we'll create it in the dispatch method
        # since db connection is required but should only be created per-request
        self.auth_service = auth_service
        self.exclude_paths = exclude_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process incoming requests.
        
        Args:
            request: Incoming request
            call_next: Next request handler
            
        Returns:
            Response: Response from next handler
        """
        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            logger.debug(f"Skipping authentication for path: {request.url.path}")
            return await call_next(request)
        
        # Get token from request
        token = self._get_token(request)
        if not token:
            logger.warning(f"No authentication token provided for path: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"}
            )
        
        try:
            # Initialize auth_service if not provided in constructor
            if self.auth_service is None:
                # Get a new db session
                async for db in get_db():
                    # Create auth service with the db session
                    auth_service = AuthService(db=db)
                    # Verify token
                    payload = await auth_service.verify_token(token)
                    
                    # Store user data in request state
                    request.state.user_id = payload.get("sub")
                    request.state.user_role = payload.get("role")
                    request.state.user_permissions = payload.get("permissions")
                    
                    # Continue with the request
                    response = await call_next(request)
                    return response
            else:
                # Use the existing auth_service
                payload = await self.auth_service.verify_token(token)
                
                # Store user data in request state
                request.state.user_id = payload.get("sub")
                request.state.user_role = payload.get("role")
                request.state.user_permissions = payload.get("permissions")
                
                # Continue with the request
                response = await call_next(request)
                return response

        except Exception as e:
            logger.error(f"Authentication error for path {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"}
            )

    def _should_skip_auth(self, request: Request) -> bool:
        """Check if authentication should be skipped for the request.
        
        Args:
            request: The incoming request
            
        Returns:
            bool: True if authentication should be skipped
        """
        path = request.url.path
        
        # Skip auth for excluded paths
        for excluded_path in self.exclude_paths:
            if path.startswith(excluded_path):
                return True
                
        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return True
            
        return False

    def _get_token(self, request: Request) -> Optional[str]:
        """Get authentication token from request.
        
        Args:
            request: The incoming request
            
        Returns:
            Optional[str]: Authentication token if present
        """
        # Try to get token from Authorization header
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            return authorization.replace("Bearer ", "")
            
        # Try to get token from cookie
        token = request.cookies.get("token")
        if token:
            return token
            
        # Try to get token from query parameters
        token = request.query_params.get("token")
        if token:
            return token
            
        return None 