"""Logging configuration module.

This module configures logging for the AI Agentic Deals System.
It provides a centralized logger configuration that can be used across the application.
"""

import logging
import sys
from typing import Dict, Any
from core.config import get_settings

settings = get_settings()

def setup_logger() -> logging.Logger:
    """Set up and configure logger."""
    # Create logger
    logger = logging.getLogger("deals")
    logger.setLevel(settings.LOG_LEVEL)

    # Create console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)
    
    # Reduce SQLAlchemy logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
    
    # Reduce aioredis logging
    logging.getLogger('aioredis').setLevel(logging.WARNING)
    
    # Reduce asyncio logging
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Reduce websockets logging
    logging.getLogger('websockets').setLevel(logging.WARNING)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(console_handler)

    return logger

# Create logger instance
logger = setup_logger()

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"deals.{name}")

def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log an error with optional context."""
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if context:
        error_data.update(context)
    logger.error("Error occurred", extra=error_data, exc_info=True)

__all__ = ["logger", "get_logger", "log_error"] 