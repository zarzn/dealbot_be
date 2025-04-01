"""Main application module."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.api.v1.router import router as api_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs" if not settings.TESTING else None,
    redoc_url="/redoc" if not settings.TESTING else None,
    # Handle trailing slashes - don't redirect
    redirect_slashes=False
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token", "X-Requested-With"],
    expose_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token", "X-Requested-With"],
)

# Add API router
app.include_router(api_router, prefix=settings.API_PREFIX)

# Add startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on shutdown.""" 