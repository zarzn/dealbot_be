import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler
import os

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

def get_logger(
    name: str,
    level: str = None,
    log_file: str = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name
        level: Log level (defaults to environment setting or INFO)
        log_file: Path to log file (optional)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    
    Returns:
        Configured logger instance
    """
    # Get logger instance
    logger = logging.getLogger(name)
    
    # Set level from environment or parameter or default to INFO
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger.setLevel(getattr(logging, log_level))

    # Create formatters
    json_formatter = JSONFormatter()
    stream_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add console handler if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(stream_formatter)
        logger.addHandler(console_handler)

    # Add file handler if log file specified and not already present
    if log_file and not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)

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

def get_request_logger(logger: logging.Logger, request_id: str) -> LoggerAdapter:
    """Get a logger adapter with request context"""
    return LoggerAdapter(logger, {"request_id": request_id})

def get_user_logger(logger: logging.Logger, user_id: str) -> LoggerAdapter:
    """Get a logger adapter with user context"""
    return LoggerAdapter(logger, {"user_id": user_id})

def get_task_logger(logger: logging.Logger, task_id: str) -> LoggerAdapter:
    """Get a logger adapter with task context"""
    return LoggerAdapter(logger, {"task_id": task_id}) 