"""Application entry point.

This module exports the FastAPI application instance for use with uvicorn.
"""

from core.main import app
import logging
from fastapi.responses import JSONResponse

# Set up logger
logger = logging.getLogger(__name__)

# Add direct health check endpoints for container health monitoring
@app.get("/health")
@app.get("/healthcheck")
@app.get("/api/healthcheck")
async def health_check():
    """Basic health check endpoint for container health monitoring.
    
    This endpoint always returns healthy and doesn't check any dependencies.
    It's designed specifically for AWS ECS health checks.
    """
    logger.info("Health check endpoint hit")
    return JSONResponse(content={"status": "healthy"})

# This file is referenced in the Docker CMD as "app:app"
# It simply exports the FastAPI application instance from main.py 