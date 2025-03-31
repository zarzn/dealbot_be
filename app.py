"""Main application entry point with FastAPI initialization."""
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Import the main application factory
from main import app as main_app

# Setup logger
logger = logging.getLogger(__name__)

# Create a FastAPI application instance
app = main_app

# No need to define health check endpoints here since they're already in main.py and router.py
# This avoids route conflicts and makes the health check structure cleaner

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get host and port from environment variables with defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    # Start the Uvicorn server
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,
        log_level="debug",
    ) 