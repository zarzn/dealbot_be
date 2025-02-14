"""Authentication middleware."""

from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings
from core.utils.logger import get_logger
from core.services.auth import AuthService
from core.exceptions.base_exceptions import AuthenticationError

logger = get_logger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for request authentication."""

    def __init__(
        self,
        app: ASGIApp,
        auth_service: Optional[AuthService] = None,
        exclude_paths: set[str] = settings.AUTH_EXCLUDE_PATHS
    ):
        super().__init__(app)
        self.auth_service = auth_service or AuthService()
        self.exclude_paths = exclude_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process the request with authentication."""
        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            return await call_next(request)

        # Get token from header
        token = self._get_token(request)
        if not token:
            logger.warning("No authentication token provided")
            raise AuthenticationError(message="No authentication token provided")

        try:
            # Verify and decode token
            user_data = await self.auth_service.verify_token(token)
            
            # Store user data in request state
            request.state.user_id = user_data.id
            request.state.user_role = user_data.role
            request.state.user_permissions = user_data.permissions

            # Check if token needs refresh
            if await self.auth_service.should_refresh_token(token):
                new_token = await self.auth_service.refresh_token(token)
                response = await call_next(request)
                response.headers["X-New-Token"] = new_token
                return response

            return await call_next(request)

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise AuthenticationError(message="Invalid or expired token")

    def _should_skip_auth(self, request: Request) -> bool:
        """Check if authentication should be skipped for this request."""
        path = request.url.path
        return any(
            path.startswith(exclude_path)
            for exclude_path in self.exclude_paths
        )

    def _get_token(self, request: Request) -> Optional[str]:
        """Extract the authentication token from the request."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1] 