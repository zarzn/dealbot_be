# Logging Strategy

## Overview

This document outlines the logging strategy for the AI Agentic Deals System. It establishes standards for consistent, informative, and actionable logging across all components of the system. Proper logging is essential for debugging, performance monitoring, security auditing, and overall system observability.

## Logging Principles

Our approach to logging is guided by these core principles:

1. **Structured Logging**: All logs should be in a structured format (JSON) for easier parsing and analysis
2. **Contextual Information**: Logs should include relevant context to make them actionable
3. **Appropriate Detail**: Log enough information to be useful without excessive verbosity
4. **Consistency**: Maintain consistent logging patterns across all components
5. **Privacy-Aware**: Never log sensitive information or personally identifiable information (PII)
6. **Performance-Conscious**: Optimize logging to minimize performance impact

## Log Levels and Usage

The system uses the following log levels, with clear guidelines for appropriate usage:

| Level | Usage | Example |
|-------|-------|---------|
| **TRACE** | Extremely detailed information, used primarily for development | Function entry/exit points with parameter values |
| **DEBUG** | Detailed information useful for debugging | Database query details, cache operations |
| **INFO** | Expected operational events and milestones | User signed up, deal created, payment processed |
| **WARNING** | Potential issues that may require attention | API rate limit at 80%, slow database query |
| **ERROR** | Errors that disrupt an operation but allow system to continue | Database query failed, external API timeout |
| **CRITICAL** | Critical errors that may prevent system operation | Database connection lost, critical service unavailable |

## Log Structure

All logs follow this standardized JSON structure:

```json
{
  "timestamp": "2023-07-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "core.services.deal_service",
  "message": "Deal created successfully",
  "request_id": "req-abc-123",
  "user_id": "user-456",
  "deal_id": "deal-789",
  "duration_ms": 123,
  "environment": "production",
  "version": "1.2.3",
  "additional_context": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

### Standard Fields

- **timestamp**: ISO 8601 format with millisecond precision and UTC timezone
- **level**: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **logger**: Name of the logger (typically module path)
- **message**: Human-readable log message
- **request_id**: Unique identifier for tracking requests across services
- **user_id**: ID of the user associated with the operation (when applicable)
- **duration_ms**: Operation duration in milliseconds (when applicable)
- **environment**: Deployment environment (development, staging, production)
- **version**: Application version
- **additional_context**: Object containing event-specific context

## Logging Implementation

### Backend (Python) Implementation

The backend uses the `structlog` library for structured logging:

```python
# core/utils/logger.py
import logging
import sys
import time
from typing import Any, Dict, Optional

import structlog
from structlog.types import Processor

from core.config import settings

# Configure processors for structlog
def add_timestamp(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add ISO 8601 timestamp to log entries."""
    event_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())[:-4]
    return event_dict

def add_environment_info(_, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add environment and version info to log entries."""
    event_dict["environment"] = settings.ENVIRONMENT
    event_dict["version"] = settings.VERSION
    return event_dict

def configure_logging() -> None:
    """Configure structured logging for the application."""
    # Set up processors
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.format_exc_info,
        add_timestamp,
        add_environment_info,
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.LOG_LEVEL),
    )

# Create the logger instance
configure_logging()
logger = structlog.get_logger()
```

### Frontend (JavaScript) Implementation

The frontend uses `winston` for server-side logging and a custom logger for client-side logging:

```typescript
// frontend/src/utils/logger.ts
import { createLogger, format, transports } from 'winston';

// Server-side logger (for Next.js API routes and server components)
export const serverLogger = createLogger({
  level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
  format: format.combine(
    format.timestamp({
      format: 'YYYY-MM-DDTHH:mm:ss.SSSZ',
    }),
    format.errors({ stack: true }),
    format.json()
  ),
  defaultMeta: {
    environment: process.env.NODE_ENV,
    version: process.env.APP_VERSION,
  },
  transports: [
    new transports.Console(),
  ],
});

// Client-side logger
export class ClientLogger {
  private static instance: ClientLogger;
  private requestId: string;
  private userId?: string;

  private constructor() {
    this.requestId = this.generateRequestId();
  }

  public static getInstance(): ClientLogger {
    if (!ClientLogger.instance) {
      ClientLogger.instance = new ClientLogger();
    }
    return ClientLogger.instance;
  }

  public setUserId(userId: string): void {
    this.userId = userId;
  }

  public setRequestId(requestId: string): void {
    this.requestId = requestId;
  }

  private generateRequestId(): string {
    return 'client-' + Math.random().toString(36).substring(2, 15);
  }

  private formatLog(level: string, message: string, data?: Record<string, any>): Record<string, any> {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      requestId: this.requestId,
      userId: this.userId,
      environment: process.env.NODE_ENV,
      version: process.env.NEXT_PUBLIC_APP_VERSION,
      ...data,
    };
  }

  public debug(message: string, data?: Record<string, any>): void {
    if (process.env.NODE_ENV !== 'production') {
      console.debug(this.formatLog('debug', message, data));
    }
  }

  public info(message: string, data?: Record<string, any>): void {
    console.info(this.formatLog('info', message, data));
  }

  public warn(message: string, data?: Record<string, any>): void {
    console.warn(this.formatLog('warn', message, data));
  }

  public error(message: string, error?: Error, data?: Record<string, any>): void {
    const logData = { ...data };
    if (error) {
      logData.error = {
        message: error.message,
        stack: error.stack,
        name: error.name,
      };
    }
    console.error(this.formatLog('error', message, logData));
    
    // In production, send errors to backend collection endpoint
    if (process.env.NODE_ENV === 'production') {
      this.sendErrorToBackend(message, error, data);
    }
  }

  private async sendErrorToBackend(message: string, error?: Error, data?: Record<string, any>): Promise<void> {
    try {
      await fetch('/api/logs/client-error', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(this.formatLog('error', message, {
          ...data,
          error: error ? {
            message: error.message,
            stack: error.stack,
            name: error.name,
          } : undefined,
        })),
      });
    } catch (e) {
      // Silent fail - we don't want to create an infinite loop of error logging
    }
  }
}

export const logger = ClientLogger.getInstance();
```

## Logging Best Practices

### What to Log

#### Authentication and Authorization

```python
# Good logging for authentication events
logger.info(
    "User logged in successfully",
    user_id=user.id,
    login_method="password",
    request_id=request_id,
    ip_address=client_ip
)

# Good logging for authorization failures
logger.warning(
    "Permission denied",
    user_id=user_id,
    requested_resource="/api/admin/users",
    required_permission="admin:read_users",
    request_id=request_id
)
```

#### Data Modifications

```python
# Good logging for data changes
logger.info(
    "Deal updated",
    user_id=user_id,
    deal_id=deal_id,
    modified_fields=["title", "price", "description"],
    request_id=request_id
)
```

#### Application Lifecycle Events

```python
# Good logging for application startup
logger.info(
    "Application started",
    version=settings.VERSION,
    environment=settings.ENVIRONMENT,
    db_connection="successful"
)
```

#### External Service Interactions

```python
# Good logging for API calls
start_time = time.time()
try:
    response = await external_api_client.get("/resource")
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "External API call successful",
        service="external_service",
        endpoint="/resource",
        status_code=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id
    )
except Exception as e:
    duration_ms = int((time.time() - start_time) * 1000)
    logger.error(
        "External API call failed",
        service="external_service",
        endpoint="/resource",
        error=str(e),
        duration_ms=duration_ms,
        request_id=request_id
    )
```

### What NOT to Log

1. **Sensitive Data**: Never log passwords, tokens, API keys, or other credentials
2. **Personal Identifiable Information (PII)**: Avoid logging full names, emails, addresses, phone numbers
3. **Financial Information**: Never log credit card numbers, bank account details
4. **Health Information**: Never log medical or health-related data
5. **Excessive Data**: Avoid logging entire request or response bodies

### Examples of Data Masking

```python
def mask_pii(email=None, phone=None, address=None):
    """Mask PII for logging purposes."""
    result = {}
    
    if email:
        parts = email.split('@')
        if len(parts) == 2:
            masked_name = parts[0][0] + '*' * (len(parts[0]) - 2) + parts[0][-1] if len(parts[0]) > 2 else parts[0][0] + '*'
            result['email'] = f"{masked_name}@{parts[1]}"
    
    if phone:
        # Keep country code and last 2 digits
        result['phone'] = phone[:3] + '*' * (len(phone) - 5) + phone[-2:] if len(phone) >= 5 else '***'
    
    if address:
        # Just indicate an address was provided but don't log any part of it
        result['address'] = '[REDACTED]'
    
    return result

# Usage
user_email = "user@example.com"
user_phone = "+1234567890"

logger.info(
    "User profile updated",
    user_id=user_id,
    **mask_pii(email=user_email, phone=user_phone),
    request_id=request_id
)
# Logs: {"message": "User profile updated", "user_id": "123", "email": "u****r@example.com", "phone": "+12*******90", "request_id": "abc123", ...}
```

## Logging Middleware

### Request Logging Middleware

```python
# core/api/middleware/request_logger.py
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.utils.logger import logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Extract request details
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent", "")
        
        # Skip logging for health check endpoints
        if path.startswith("/health"):
            response = await call_next(request)
            return response
        
        # Log request
        logger.info(
            f"Request started: {method} {path}",
            request_id=request_id,
            http_method=method,
            path=path,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        # Process request and measure time
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed: {method} {path}",
                request_id=request_id,
                http_method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2)
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            logger.exception(
                f"Request failed: {method} {path}",
                request_id=request_id,
                http_method=method,
                path=path,
                error=str(exc),
                duration_ms=round(process_time * 1000, 2)
            )
            raise
```

## Log Collection and Storage

### Log Aggregation Architecture

The system uses a multi-tier approach to log collection and storage:

1. **Application Logs**: Generated by application components
2. **Log Forwarder**: Collects logs from all components
3. **Log Aggregator**: Centralizes logs for processing
4. **Log Storage**: Long-term archival and analysis

### AWS CloudWatch Implementation

```python
# core/utils/logger.py (CloudWatch integration)
import watchtower
import boto3

# Configure CloudWatch logging
def setup_cloudwatch_logging():
    if settings.ENABLE_CLOUDWATCH_LOGS:
        # Create CloudWatch client
        cloudwatch_client = boto3.client(
            'logs',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Create CloudWatch handler
        cloudwatch_handler = watchtower.CloudWatchLogHandler(
            log_group=f"{settings.APP_NAME}-{settings.ENVIRONMENT}",
            stream_name=f"{settings.SERVICE_NAME}-{settings.VERSION}",
            create_log_group=True,
            boto3_client=cloudwatch_client
        )
        
        # Add CloudWatch handler to the root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(cloudwatch_handler)
        
        return cloudwatch_handler
    return None

# Initialize CloudWatch logging
cloudwatch_handler = setup_cloudwatch_logging()
```

### Log Retention Policy

| Log Type | Retention Period | Storage Location |
|----------|------------------|------------------|
| Application logs | 30 days | CloudWatch Logs |
| Security logs | 1 year | CloudWatch Logs + S3 Archive |
| Error logs | 90 days | CloudWatch Logs |
| Access logs | 90 days | CloudWatch Logs |
| Performance metrics | 1 year | CloudWatch Metrics |

## Log Analysis and Monitoring

### CloudWatch Dashboards

The system uses CloudWatch Dashboards for real-time monitoring:

1. **Operational Dashboard**: Overall system health and performance
2. **Error Dashboard**: Error rates and patterns
3. **Security Dashboard**: Authentication and authorization events
4. **Performance Dashboard**: Response times and resource utilization

### CloudWatch Alarms

Key metrics have associated alarms:

1. **Error Rate Alarms**: Trigger when error rates exceed thresholds
2. **Latency Alarms**: Alert on slow response times
3. **Security Alarms**: Detect suspicious authentication patterns
4. **Resource Alarms**: Monitor resource utilization

### Log Query Examples

```
# Find all errors for a specific request
fields @timestamp, @message, error
| filter request_id = "req-abc-123"
| filter level = "ERROR"
| sort @timestamp desc

# Calculate API error rates
fields @timestamp
| filter @message like "Request completed"
| stats count(*) as total, 
    count(*) as total_requests by status_code
| filter status_code >= 400
| sort total desc

# Track slow database queries
fields @timestamp, query, duration_ms, user_id
| filter duration_ms > 500
| sort duration_ms desc
| limit 20
```

## AI Component Logging

AI components require specialized logging considerations:

### LLM Request and Response Logging

```python
# Good LLM interaction logging
async def generate_completion(prompt: str, **kwargs):
    # Sanitize prompt for logging (remove PII)
    sanitized_prompt = sanitize_prompt_for_logging(prompt)
    
    logger.info(
        "LLM request initiated",
        prompt_length=len(prompt),
        prompt_preview=sanitized_prompt[:100] + "..." if len(sanitized_prompt) > 100 else sanitized_prompt,
        model=kwargs.get("model", "default"),
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 1000),
        request_id=request_id
    )
    
    start_time = time.time()
    try:
        response = await llm_provider.completion(prompt, **kwargs)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Sanitize response for logging
        sanitized_response = sanitize_response_for_logging(response)
        
        logger.info(
            "LLM request completed",
            prompt_length=len(prompt),
            response_length=len(response),
            response_preview=sanitized_response[:100] + "..." if len(sanitized_response) > 100 else sanitized_response,
            token_count=count_tokens(prompt, response),
            duration_ms=duration_ms,
            model=kwargs.get("model", "default"),
            request_id=request_id
        )
        return response
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "LLM request failed",
            error=str(e),
            prompt_length=len(prompt),
            duration_ms=duration_ms,
            model=kwargs.get("model", "default"),
            request_id=request_id
        )
        raise
```

### Token Usage Logging

```python
# Good token usage logging
logger.info(
    "Tokens deducted from user balance",
    user_id=user_id,
    deducted_amount=token_amount,
    transaction_type="ai_completion",
    new_balance=remaining_balance,
    operation_id=operation_id,
    request_id=request_id
)
```

## Development Guidelines

### Logging in Development

1. **Local Log Configuration**:
   - Set `LOG_LEVEL=DEBUG` for detailed logs
   - Use console output for immediate feedback
   - Structure preserved but formatted for readability

2. **Development Tools**:
   - Configure IDE integration for log visualization
   - Use log analyzers for troubleshooting

### Testing Logging

1. **Unit Tests for Logging**:
   - Verify critical events are logged
   - Ensure correct log levels
   - Check context inclusion

2. **Example Test**:

```python
# tests/utils/test_logging.py
import pytest
from unittest.mock import patch, MagicMock

from core.services.user_service import UserService
from core.utils.logger import logger

@pytest.mark.asyncio
async def test_user_creation_logging():
    # Arrange
    mock_logger = MagicMock()
    user_service = UserService()
    user_data = {
        "email": "test@example.com",
        "password": "securePassword123",
        "name": "Test User"
    }
    
    # Act
    with patch('core.services.user_service.logger', mock_logger):
        user = await user_service.create_user(**user_data)
    
    # Assert
    mock_logger.info.assert_called_once()
    log_call = mock_logger.info.call_args[0]
    
    # Check message
    assert "User created successfully" in log_call[0]
    
    # Check context
    log_kwargs = mock_logger.info.call_args[1]
    assert log_kwargs.get("user_id") == str(user.id)
    assert "email" not in log_kwargs  # Should not log PII
    assert "password" not in log_kwargs  # Should never log password
```

## References

1. [AWS CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html)
2. [Structlog Documentation](https://www.structlog.org/en/stable/)
3. [Winston Documentation](https://github.com/winstonjs/winston)
4. [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
5. [Google Cloud Logging Best Practices](https://cloud.google.com/logging/docs/best-practices)
6. [Error Handling Documentation](../development/error_handling.md)
7. [Monitoring Strategy](../monitoring/overview.md) 