from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from core.database.init_db import init_database
from core.api.v1.router import router as api_v1_router
from core.api.v1.notifications.websocket import handle_websocket

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialization completed")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down application...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered deal monitoring system",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include API router
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

# WebSocket endpoint
app.websocket("/notifications/ws")(handle_websocket)

@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {"status": "ok"}
