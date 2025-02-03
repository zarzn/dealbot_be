"""Logging utility functions."""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler
import os
from core.config import get_settings

settings = get_settings()

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if available
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack info if available
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_data)

def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        logger.setLevel(settings.LOG_LEVEL)
    
    return logger

class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context to logs"""
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        """Initialize adapter with logger and extra context"""
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add extra context"""
        # Ensure kwargs has extra dict
        kwargs.setdefault("extra", {})
        
        # Add adapter extra to kwargs extra
        kwargs["extra"].update(self.extra)
        
        return msg, kwargs

def get_request_logger(logger: logging.Logger, request_id: str) -> Any:
    """Get logger with request context."""
    return logging.LoggerAdapter(
        logger,
        {'request_id': request_id}
    )

def get_user_logger(logger: logging.Logger, user_id: str) -> LoggerAdapter:
    """Get a logger adapter with user context"""
    return LoggerAdapter(logger, {"user_id": user_id})

def get_task_logger(logger: logging.Logger, task_id: str) -> LoggerAdapter:
    """Get a logger adapter with task context"""
    return LoggerAdapter(logger, {"task_id": task_id}) 