# Error Handling Standards

## Overview

This document outlines the standard error handling practices for the AI Agentic Deals System. It provides guidelines for consistent, informative, and actionable error management across all components of the system. Following these standards ensures better debugging, user experience, and system reliability.

## Error Handling Philosophy

Our approach to error handling is guided by these principles:

1. **Fail Fast, Fail Visibly**: Detect and report errors as early as possible
2. **Actionable Information**: Error messages should help users and developers understand what went wrong and how to fix it
3. **Graceful Degradation**: System should continue functioning when possible, with appropriate fallbacks
4. **Security First**: Never expose sensitive information in error messages to end users
5. **Centralized Handling**: Consistent error handling patterns across the system
6. **Proper Categorization**: Distinguish between different error types for appropriate responses

## Error Categories

The system categorizes errors into the following types:

### 1. Validation Errors

Issues with input data that prevent processing.

- **HTTP Status Code**: 400 Bad Request
- **Internal Code Prefix**: `VALIDATION_`
- **Handling Strategy**: Return detailed information about validation failures
- **Example**: Invalid email format, missing required field

### 2. Authentication Errors

Issues with user identity verification.

- **HTTP Status Code**: 401 Unauthorized
- **Internal Code Prefix**: `AUTH_`
- **Handling Strategy**: Redirect to login or request reauthentication
- **Example**: Expired token, invalid credentials

### 3. Authorization Errors

Issues with user permissions.

- **HTTP Status Code**: 403 Forbidden
- **Internal Code Prefix**: `FORBIDDEN_`
- **Handling Strategy**: Inform user about insufficient permissions
- **Example**: Attempting to access another user's data

### 4. Resource Errors

Issues with requested resources.

- **HTTP Status Code**: 404 Not Found
- **Internal Code Prefix**: `RESOURCE_`
- **Handling Strategy**: Inform user about missing resource
- **Example**: Requested deal not found

### 5. Conflict Errors

Issues with conflicting operations.

- **HTTP Status Code**: 409 Conflict
- **Internal Code Prefix**: `CONFLICT_`
- **Handling Strategy**: Explain the conflict and suggest resolution
- **Example**: Attempting to create a duplicate resource

### 6. Rate Limit Errors

Issues with exceeding usage limits.

- **HTTP Status Code**: 429 Too Many Requests
- **Internal Code Prefix**: `RATE_LIMIT_`
- **Handling Strategy**: Inform user when they can retry
- **Example**: Too many API requests in a short period

### 7. Integration Errors

Issues with external service integration.

- **HTTP Status Code**: 502 Bad Gateway
- **Internal Code Prefix**: `INTEGRATION_`
- **Handling Strategy**: Retry with backoff, fallback, or notify user
- **Example**: External API returning errors

### 8. System Errors

Internal issues with the application.

- **HTTP Status Code**: 500 Internal Server Error
- **Internal Code Prefix**: `SYSTEM_`
- **Handling Strategy**: Log details, notify developers, provide generic message to users
- **Example**: Unhandled exception, database connection failure

### 9. Token System Errors

Issues specific to the token system.

- **HTTP Status Code**: 402 Payment Required
- **Internal Code Prefix**: `TOKEN_`
- **Handling Strategy**: Inform user about token requirements or issues
- **Example**: Insufficient token balance for an operation

### 10. AI Processing Errors

Issues specific to AI services.

- **HTTP Status Code**: 422 Unprocessable Entity
- **Internal Code Prefix**: `AI_`
- **Handling Strategy**: Fallback to alternative model or simplified processing
- **Example**: LLM timeout, invalid AI response format

## Error Response Format

All API error responses follow this consistent JSON format:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field_name": "Field-specific error details",
    "additional_info": "Context-specific error information"
  },
  "request_id": "unique-request-identifier",
  "timestamp": "2023-07-15T10:30:45Z"
}
```

- **status**: Always "error" for error responses
- **code**: Unique error code (prefixed as per error category)
- **message**: User-friendly error message
- **details**: Optional object with error specifics
- **request_id**: Unique identifier for the request (for correlation with logs)
- **timestamp**: When the error occurred (UTC)

## Implementation Guidelines

### Backend Implementation

#### Base Error Classes

The system uses a hierarchy of error classes inherited from a base `AppError` class:

```python
# core/exceptions/base.py
from typing import Any, Dict, Optional, Type

class AppError(Exception):
    """Base exception class for all application errors."""
    
    status_code: int = 500
    code: str = "SYSTEM_ERROR"
    message: str = "An unexpected error occurred."
    
    def __init__(
        self, 
        message: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None
    ):
        self.message = message or self.message
        self.details = details or {}
        self.code = code or self.code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for API responses."""
        return {
            "status": "error",
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class ValidationError(AppError):
    """Exception raised for validation errors."""
    
    status_code: int = 400
    code: str = "VALIDATION_ERROR"
    message: str = "Invalid input data."


class AuthenticationError(AppError):
    """Exception raised for authentication failures."""
    
    status_code: int = 401
    code: str = "AUTH_ERROR"
    message: str = "Authentication required."


class AuthorizationError(AppError):
    """Exception raised for permission issues."""
    
    status_code: int = 403
    code: str = "FORBIDDEN_ERROR"
    message: str = "You don't have permission to perform this action."


class ResourceNotFoundError(AppError):
    """Exception raised when a requested resource doesn't exist."""
    
    status_code: int = 404
    code: str = "RESOURCE_NOT_FOUND"
    message: str = "The requested resource was not found."


class ConflictError(AppError):
    """Exception raised for conflicting operations."""
    
    status_code: int = 409
    code: str = "CONFLICT_ERROR"
    message: str = "This operation conflicts with the current state."


class RateLimitError(AppError):
    """Exception raised when rate limits are exceeded."""
    
    status_code: int = 429
    code: str = "RATE_LIMIT_EXCEEDED"
    message: str = "Too many requests. Please try again later."
    
    def __init__(
        self, 
        message: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(message, details, code)
        self.retry_after = retry_after


class IntegrationError(AppError):
    """Exception raised for external service integration issues."""
    
    status_code: int = 502
    code: str = "INTEGRATION_ERROR"
    message: str = "Error communicating with external service."


class SystemError(AppError):
    """Exception raised for internal system errors."""
    
    status_code: int = 500
    code: str = "SYSTEM_ERROR"
    message: str = "An internal system error occurred."


class TokenError(AppError):
    """Exception raised for token-related issues."""
    
    status_code: int = 402
    code: str = "TOKEN_ERROR"
    message: str = "Token-related operation failed."


class AIProcessingError(AppError):
    """Exception raised for AI processing issues."""
    
    status_code: int = 422
    code: str = "AI_PROCESSING_ERROR"
    message: str = "Error processing AI request."
```

#### Global Exception Handler

FastAPI's exception handler captures and formats all errors:

```python
# core/api/error_handlers.py
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions.base import AppError
from core.utils.logger import logger

def setup_error_handlers(app: FastAPI) -> None:
    """Configure global exception handlers for the application."""
    
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle custom application errors."""
        error_dict = exc.to_dict()
        error_dict["request_id"] = request.state.request_id
        error_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Log the error
        logger.error(
            f"AppError: {exc.code} - {exc.message}",
            extra={
                "request_id": request.state.request_id,
                "status_code": exc.status_code,
                "error_code": exc.code,
                "error_details": exc.details,
                "path": request.url.path
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_dict
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        error_dict = {
            "status": "error",
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": {},
            "request_id": request.state.request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        logger.error(
            f"HTTPException: {exc.status_code} - {exc.detail}",
            extra={
                "request_id": request.state.request_id,
                "status_code": exc.status_code,
                "path": request.url.path
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_dict
        )
    
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled exceptions."""
        error_id = str(uuid.uuid4())
        error_dict = {
            "status": "error",
            "code": "SYSTEM_UNHANDLED_ERROR",
            "message": "An unexpected error occurred.",
            "details": {"error_id": error_id},
            "request_id": request.state.request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        # Log the full exception details for debugging
        logger.exception(
            f"Unhandled exception: {str(exc)}",
            extra={
                "request_id": request.state.request_id,
                "error_id": error_id,
                "path": request.url.path
            }
        )
        
        return JSONResponse(
            status_code=500,
            content=error_dict
        )
    
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add a unique request ID to each request for tracing."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### Frontend Implementation

#### API Client Error Handling

The frontend uses a centralized API client that handles errors consistently:

```typescript
// frontend/src/services/api/client.ts
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { ErrorResponse } from './types';
import { refreshToken } from '../auth/tokenService';
import { store } from '../../store';
import { showErrorNotification } from '../../store/slices/uiSlice';

export class ApiClient {
  private static instance: ApiClient;
  private client: AxiosInstance;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  private constructor() {
    this.client = axios.create({
      baseURL: process.env.REACT_APP_API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  public static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient();
    }
    return ApiClient.instance;
  }

  private setupInterceptors(): void {
    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle errors
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ErrorResponse>) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
        
        // Handle token expiration
        if (error.response?.status === 401 && !originalRequest._retry) {
          if (error.response.data.code === 'AUTH_TOKEN_EXPIRED') {
            return this.handleTokenRefresh(originalRequest);
          }
        }
        
        // Handle other errors
        this.handleError(error);
        return Promise.reject(error);
      }
    );
  }

  private async handleTokenRefresh(originalRequest: AxiosRequestConfig & { _retry?: boolean }): Promise<AxiosResponse> {
    if (!this.isRefreshing) {
      this.isRefreshing = true;
      
      try {
        const newToken = await refreshToken();
        this.isRefreshing = false;
        
        // Retry original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        originalRequest._retry = true;
        
        // Process any queued requests
        this.refreshSubscribers.forEach((callback) => callback(newToken));
        this.refreshSubscribers = [];
        
        return this.client(originalRequest);
      } catch (error) {
        this.isRefreshing = false;
        
        // Token refresh failed, redirect to login
        store.dispatch({ type: 'auth/logout' });
        window.location.href = '/login?session_expired=true';
        
        return Promise.reject(error);
      }
    } else {
      // Queue request while refresh is in progress
      return new Promise((resolve) => {
        this.refreshSubscribers.push((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          originalRequest._retry = true;
          resolve(this.client(originalRequest));
        });
      });
    }
  }

  private handleError(error: AxiosError<ErrorResponse>): void {
    const errorResponse = error.response?.data;
    
    if (errorResponse) {
      // Log error for debugging
      console.error(`API Error: ${errorResponse.code} - ${errorResponse.message}`, {
        requestId: errorResponse.request_id,
        details: errorResponse.details,
        timestamp: errorResponse.timestamp
      });
      
      // Show user-friendly notification
      const shouldShowToUser = this.shouldShowErrorToUser(error.response?.status || 500, errorResponse.code);
      
      if (shouldShowToUser) {
        store.dispatch(showErrorNotification({
          title: this.getErrorTitle(errorResponse.code),
          message: errorResponse.message,
          details: errorResponse.details,
          code: errorResponse.code
        }));
      }
    } else {
      // Network error or unexpected error format
      console.error('Network Error:', error);
      store.dispatch(showErrorNotification({
        title: 'Connection Error',
        message: 'Unable to connect to the server. Please check your internet connection.',
        code: 'NETWORK_ERROR'
      }));
    }
  }

  private shouldShowErrorToUser(statusCode: number, errorCode: string): boolean {
    // Don't show authentication errors (handled by auth flow)
    if (statusCode === 401) return false;
    
    // Don't show certain system errors to users
    if (errorCode.startsWith('SYSTEM_')) return false;
    
    return true;
  }

  private getErrorTitle(errorCode: string): string {
    if (errorCode.startsWith('VALIDATION_')) return 'Invalid Input';
    if (errorCode.startsWith('AUTH_')) return 'Authentication Error';
    if (errorCode.startsWith('FORBIDDEN_')) return 'Permission Denied';
    if (errorCode.startsWith('RESOURCE_')) return 'Resource Error';
    if (errorCode.startsWith('CONFLICT_')) return 'Conflict Error';
    if (errorCode.startsWith('RATE_LIMIT_')) return 'Rate Limit Exceeded';
    if (errorCode.startsWith('INTEGRATION_')) return 'Service Unavailable';
    if (errorCode.startsWith('TOKEN_')) return 'Token Error';
    if (errorCode.startsWith('AI_')) return 'AI Processing Error';
    
    return 'Error';
  }

  // Public API methods
  public async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  public async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  public async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  public async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }
}

export const apiClient = ApiClient.getInstance();
```

#### Error Boundary Component

React Error Boundaries catch and handle UI rendering errors:

```tsx
// frontend/src/components/common/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button, Result } from 'antd';
import { logger } from '../../utils/logger';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to monitoring service
    logger.error('UI Error Boundary caught an error', {
      error: error.toString(),
      stack: error.stack,
      componentStack: errorInfo.componentStack,
    });
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Result
          status="error"
          title="Something went wrong"
          subTitle="The application encountered an unexpected error."
          extra={[
            <Button key="refresh" type="primary" onClick={() => window.location.reload()}>
              Refresh Page
            </Button>,
            <Button key="reset" onClick={this.handleReset}>
              Try Again
            </Button>,
          ]}
        />
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

## AI Service Error Handling

AI services require specialized error handling due to their probabilistic nature and external dependencies.

### LLM Error Recovery Strategy

```python
# core/services/ai/llm_service.py
import time
from typing import Any, Dict, List, Optional
import asyncio

from core.exceptions.base import AIProcessingError, IntegrationError
from core.services.ai.models import LLMProvider
from core.utils.logger import logger

class LLMService:
    """Service for handling LLM interactions with fallback capabilities."""
    
    def __init__(self, primary_provider: LLMProvider, fallback_provider: Optional[LLMProvider] = None):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.max_retries = 3
        self.retry_delay = 1  # seconds
    
    async def generate_completion(
        self, 
        prompt: str, 
        temperature: float = 0.7, 
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Generate text completion with retry and fallback logic.
        """
        # Try primary provider with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self.primary_provider.generate_completion(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as e:
                logger.warning(
                    f"Primary LLM provider error (attempt {attempt}/{self.max_retries}): {str(e)}",
                    extra={"provider": self.primary_provider.name}
                )
                
                if attempt == self.max_retries:
                    # Last attempt failed, try fallback if available
                    if self.fallback_provider:
                        logger.info(
                            f"Attempting fallback LLM provider after {self.max_retries} failed primary attempts",
                            extra={"primary_provider": self.primary_provider.name, "fallback_provider": self.fallback_provider.name}
                        )
                        try:
                            return await self.fallback_provider.generate_completion(
                                prompt=prompt,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                        except Exception as fallback_error:
                            logger.error(
                                f"Fallback LLM provider also failed: {str(fallback_error)}",
                                extra={"provider": self.fallback_provider.name}
                            )
                            raise AIProcessingError(
                                message="All LLM providers failed to process the request.",
                                details={
                                    "primary_error": str(e),
                                    "fallback_error": str(fallback_error)
                                }
                            )
                    else:
                        # No fallback available
                        if isinstance(e, (ConnectionError, TimeoutError)):
                            raise IntegrationError(
                                message="Unable to connect to AI service. Please try again later.",
                                details={"provider": self.primary_provider.name}
                            )
                        else:
                            raise AIProcessingError(
                                message="AI processing service is currently experiencing issues.",
                                details={"original_error": str(e)}
                            )
                
                # Not last attempt, wait before retry
                await asyncio.sleep(self.retry_delay * attempt)  # Exponential backoff
    
    async def validate_ai_response(self, response: str, expected_format: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that AI response matches expected format.
        """
        try:
            import json
            parsed_response = json.loads(response)
            
            # Basic schema validation
            for key, type_info in expected_format.items():
                if key not in parsed_response:
                    raise AIProcessingError(
                        message="AI response is missing required fields.",
                        details={"missing_field": key}
                    )
                
                # Type checking logic would go here
                
            return parsed_response
        except json.JSONDecodeError:
            raise AIProcessingError(
                message="AI response is not valid JSON.",
                details={"response_excerpt": response[:100] + "..." if len(response) > 100 else response}
            )
```

## Token System Error Handling

The token system requires specialized error handling to manage transaction failures and balance issues.

### Token Transaction Error Handling

```python
# core/services/token/token_service.py
from typing import Optional, Dict, Any
from uuid import UUID
import asyncio
from fastapi import HTTPException, status

from core.exceptions.base import TokenError, ConflictError, SystemError
from core.models.token import UserTokenBalance, TokenTransaction
from core.models.enums import TokenTransactionType
from core.utils.logger import logger
from core.db.transactions import transaction

class InsufficientTokensError(TokenError):
    """Error for insufficient token balance."""
    
    code = "TOKEN_INSUFFICIENT_BALANCE"
    message = "Insufficient token balance for this operation."


class TokenService:
    """Service for managing user tokens and token transactions."""
    
    @transaction()
    async def deduct_tokens(
        self, 
        user_id: UUID, 
        amount: int, 
        transaction_type: TokenTransactionType,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reference_id: Optional[UUID] = None
    ) -> int:
        """
        Deduct tokens from a user's balance with proper error handling.
        """
        if amount <= 0:
            raise ValueError("Token amount must be positive")
            
        # Get user balance
        balance = await UserTokenBalance.get_or_create(user_id)
        
        # Ensure sufficient balance
        if balance.balance < amount:
            current_balance = balance.balance
            raise InsufficientTokensError(
                message=f"Insufficient token balance. Required: {amount}, Available: {current_balance}",
                details={
                    "required_amount": amount,
                    "available_balance": current_balance,
                    "missing_amount": amount - current_balance
                }
            )
        
        try:
            # Update balance
            balance.balance -= amount
            balance.lifetime_spent += amount
            await balance.save()
            
            # Record transaction
            await TokenTransaction.create(
                user_id=user_id,
                transaction_type=transaction_type.value.lower(),
                amount=-amount,  # Negative for deductions
                balance_after=balance.balance,
                description=description,
                metadata=metadata,
                reference_id=reference_id
            )
            
            logger.info(
                f"Deducted {amount} tokens from user {user_id}",
                extra={
                    "user_id": str(user_id),
                    "amount": amount,
                    "transaction_type": transaction_type.value,
                    "new_balance": balance.balance
                }
            )
            
            return balance.balance
        except Exception as e:
            # This shouldn't happen due to transaction decorator, but just in case
            logger.exception(
                f"Failed to deduct tokens: {str(e)}",
                extra={
                    "user_id": str(user_id),
                    "amount": amount,
                    "transaction_type": transaction_type.value
                }
            )
            raise SystemError(
                message="Failed to process token transaction",
                details={"original_error": str(e)}
            )
```

## Logging and Monitoring

### Log Levels and Usage

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Detailed diagnostic information | `logger.debug("Processing deal data", extra={"deal_id": deal_id})` |
| INFO | Expected operational events | `logger.info("User authenticated", extra={"user_id": user_id})` |
| WARNING | Potential issues that may need attention | `logger.warning("API rate limit at 80%", extra={"limit": limit, "usage": usage})` |
| ERROR | Errors that interrupt an operation | `logger.error("Failed to process payment", extra={"error": str(e), "user_id": user_id})` |
| CRITICAL | System-wide failures requiring immediate attention | `logger.critical("Database connection failed", extra={"connection_id": conn_id})` |

### Error Logging Best Practices

1. **Include Context**: Always include relevant context with error logs
2. **Structured Logging**: Use structured logging for easier analysis
3. **Correlation IDs**: Include request IDs to correlate logs across services
4. **PII Handling**: Never log sensitive information (passwords, tokens, etc.)
5. **Stack Traces**: Include stack traces for debugging but limit in production

### Monitoring Integration

Errors are integrated with monitoring systems:

1. **CloudWatch Metrics**: Track error rates and categories
2. **CloudWatch Alarms**: Alert on error thresholds
3. **Slack Notifications**: Real-time alerts for critical errors
4. **Error Dashboards**: Visualize error patterns and trends

## Error Prevention Best Practices

### Input Validation

1. **Use Pydantic Models**: Leverage Pydantic for request validation
2. **Validate Early**: Validate inputs as early as possible
3. **Be Specific**: Provide clear validation rules
4. **Custom Validators**: Implement domain-specific validation

Example:
```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class CreateDealRequest(BaseModel):
    """Request model for creating a deal."""
    
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0)
    
    @validator('title')
    def title_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty or just whitespace")
        return v
```

### Database Operations

1. **Use Transactions**: Wrap related operations in database transactions
2. **Handle Constraint Violations**: Catch and handle database constraint violations
3. **Retry Transient Errors**: Implement retry logic for transient database errors
4. **Validate Before Writing**: Validate data before database operations

Example:
```python
from core.db.transactions import transaction
from core.exceptions.base import ConflictError

@transaction()
async def create_user(email: str, password: str, name: str):
    try:
        # Check if user exists
        existing_user = await User.get_by_email(email)
        if existing_user:
            raise ConflictError(
                message="A user with this email already exists",
                code="USER_EMAIL_EXISTS"
            )
        
        # Create user
        user = User(
            email=email,
            hashed_password=hash_password(password),
            name=name
        )
        await user.save()
        return user
    except UniqueViolationError:
        # Catch potential race condition
        raise ConflictError(
            message="A user with this email already exists",
            code="USER_EMAIL_EXISTS"
        )
```

### Concurrency Handling

1. **Use Locks**: Use distributed locks for critical operations
2. **Optimistic Concurrency**: Implement version-based concurrency control
3. **Idempotent Operations**: Design APIs to be idempotent when possible
4. **Rate Limiting**: Implement rate limiting to prevent overload

Example:
```python
import asyncio
from core.services.redis import get_redis_service

async def with_lock(key: str, ttl: int = 30):
    """Decorator for distributed locking using Redis."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            redis = await get_redis_service()
            lock_key = f"lock:{key}"
            
            # Try to acquire lock
            lock_acquired = await redis.set(lock_key, "1", nx=True, ex=ttl)
            if not lock_acquired:
                raise ConflictError(
                    message="Operation in progress. Please try again later.",
                    code="RESOURCE_LOCKED"
                )
            
            try:
                return await func(*args, **kwargs)
            finally:
                # Release lock
                await redis.delete(lock_key)
        return wrapper
    return decorator
```

## Testing Error Scenarios

### Unit Tests

Test all error conditions in unit tests:

```python
# tests/unit/services/test_token_service.py
import pytest
from uuid import uuid4

from core.services.token.token_service import TokenService, InsufficientTokensError
from core.models.enums import TokenTransactionType

@pytest.mark.asyncio
async def test_deduct_tokens_insufficient_balance():
    # Arrange
    user_id = uuid4()
    token_service = TokenService()
    
    # Create user with 10 tokens
    await token_service.add_tokens(
        user_id=user_id,
        amount=10,
        transaction_type=TokenTransactionType.SIGNUP_BONUS,
        description="Signup bonus"
    )
    
    # Act & Assert
    with pytest.raises(InsufficientTokensError) as exc_info:
        await token_service.deduct_tokens(
            user_id=user_id,
            amount=20,  # More than available
            transaction_type=TokenTransactionType.AI_USAGE,
            description="AI analysis"
        )
    
    # Verify error details
    assert exc_info.value.details["required_amount"] == 20
    assert exc_info.value.details["available_balance"] == 10
    assert exc_info.value.details["missing_amount"] == 10
```

### Integration Tests

Test error handling across component boundaries:

```python
# tests/integration/api/test_token_api.py
import pytest
from httpx import AsyncClient

from core.models.enums import TokenTransactionType
from tests.factories.user_factory import UserFactory
from tests.factories.token_factory import TokenBalanceFactory

@pytest.mark.asyncio
async def test_token_deduction_api_insufficient_balance(client: AsyncClient, auth_headers):
    # Arrange
    user = await UserFactory.create()
    await TokenBalanceFactory.create(user=user, balance=5)
    
    # Act
    response = await client.post(
        "/api/v1/tokens/deduct",
        json={
            "amount": 10,
            "transaction_type": TokenTransactionType.AI_USAGE.value,
            "description": "AI analysis"
        },
        headers=auth_headers(user)
    )
    
    # Assert
    assert response.status_code == 402
    data = response.json()
    assert data["code"] == "TOKEN_INSUFFICIENT_BALANCE"
    assert "Required: 10, Available: 5" in data["message"]
    assert data["details"]["missing_amount"] == 5
```

## References

1. [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
2. [Python Exception Best Practices](https://docs.python.org/3/tutorial/errors.html)
3. [React Error Boundaries](https://reactjs.org/docs/error-boundaries.html)
4. [OWASP Error Handling Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html)
5. [System Architecture Overview](../architecture/architecture.md) 