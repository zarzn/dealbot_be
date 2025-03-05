# API Documentation Overview

## Introduction
The AI Agentic Deals System API is built using FastAPI and follows RESTful principles. The API provides endpoints for user management, goal tracking, deal monitoring, and token operations.

## Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://api.deals.example.com/api/v1`

## API Versioning
The API uses semantic versioning in the URL path (e.g., `/api/v1/`). This ensures backward compatibility and smooth transitions during updates.

## Authentication
All authenticated endpoints require a valid JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Response Format
### Success Response
```json
{
    "status": "success",
    "data": <response_data>,
    "message": "Optional success message"
}
```

### Error Response
```json
{
    "status": "error",
    "error": {
        "code": "ERROR_CODE",
        "message": "User-friendly error message",
        "details": {
            "technical_details": "Additional error information"
        },
        "context": {
            "request_id": "unique_request_id"
        }
    }
}
```

## Pagination
Paginated endpoints use the following format:
```json
{
    "items": [],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
}
```

## Rate Limiting
- Standard rate limit: 100 requests per minute
- Authenticated rate limit: 1000 requests per minute
- Token operations: 50 requests per minute

## Core Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `POST /auth/refresh-token` - Refresh access token
- `POST /auth/reset-password` - Password reset
- `POST /auth/verify-email` - Email verification

### User Management
- `GET /users/me` - Get current user profile
- `PUT /users/me` - Update user profile
- `GET /users/preferences` - Get user preferences
- `PUT /users/preferences` - Update user preferences
- `GET /users/notifications` - Get user notifications
- `PUT /users/notifications/settings` - Update notification settings

### Goal Management
- `GET /goals` - List user goals
- `POST /goals` - Create new goal
- `GET /goals/{goal_id}` - Get goal details
- `PUT /goals/{goal_id}` - Update goal
- `DELETE /goals/{goal_id}` - Delete goal
- `GET /goals/{goal_id}/deals` - List deals for goal
- `POST /goals/{goal_id}/pause` - Pause goal monitoring
- `POST /goals/{goal_id}/resume` - Resume goal monitoring

### Deal Management
- `GET /deals` - List all deals
- `GET /deals/{deal_id}` - Get deal details
- `GET /deals/{deal_id}/price-history` - Get price history
- `POST /deals/{deal_id}/track` - Start tracking deal
- `DELETE /deals/{deal_id}/track` - Stop tracking deal

### Price Tracking
- `GET /price-tracking/trackers` - List price trackers
- `POST /price-tracking/trackers` - Create price tracker
- `GET /price-tracking/trackers/{tracker_id}` - Get tracker details
- `PUT /price-tracking/trackers/{tracker_id}` - Update tracker
- `DELETE /price-tracking/trackers/{tracker_id}` - Delete tracker
- `GET /price-tracking/history/{deal_id}` - Get price history

### Token Operations
- `GET /token/balance` - Get token balance
- `GET /token/transactions` - List token transactions
- `POST /token/connect-wallet` - Connect wallet
- `POST /token/disconnect-wallet` - Disconnect wallet

### WebSocket Endpoints
- `WS /notifications/ws` - Real-time notifications and updates

### System Health
- `GET /health` - Basic health check
- `GET /health/db` - Database health
- `GET /health/redis` - Redis health
- `GET /health/services` - External services health

## Documentation Endpoints
The API documentation is available through Swagger UI and ReDoc:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI Schema: `/openapi.json`

## Error Codes
Common error codes and their meanings:
- `AUTH_001` - Authentication failed
- `AUTH_002` - Token expired
- `AUTH_003` - Invalid token
- `GOAL_001` - Goal creation failed
- `GOAL_002` - Goal not found
- `DEAL_001` - Deal not found
- `TOKEN_001` - Insufficient balance
- `TOKEN_002` - Transaction failed

## Best Practices
1. Always include appropriate error handling
2. Use pagination for large result sets
3. Cache frequently accessed data
4. Implement proper rate limiting
5. Monitor API performance
6. Log all significant operations

## API Clients
Example API clients are available for:
- Python
- JavaScript/TypeScript
- Dart/Flutter

## Support
For API support or to report issues:
1. Check the documentation
2. Review common issues in troubleshooting
3. Contact the development team
4. Create an issue in the repository 

# API Overview

This document provides a comprehensive overview of the API endpoints for the AI Agentic Deals System.

## API Structure

The API follows REST principles and is organized around resources. All requests and responses use JSON format. The API is versioned to ensure backward compatibility.

Base URL: `https://api.example.com/v1`

## Authentication

All API requests (except for authentication endpoints) require authentication using JWT (JSON Web Token) Bearer authentication.

### Authentication Flow

1. Client obtains a JWT token by authenticating via `/auth/login`
2. Client includes the token in the Authorization header for all subsequent requests
3. Token expires after a set period (default: 1 hour)
4. Client can refresh the token using `/auth/refresh` before expiration
5. Token can be invalidated using `/auth/logout`

Example:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Rate Limiting

API requests are subject to rate limiting to prevent abuse:
- Standard limit: 100 requests per minute
- Authenticated users may have higher limits based on their subscription
- Token-based operations have specific limits to prevent token abuse

Rate limit headers are included in all responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1677694800
```

## Error Handling

The API uses standard HTTP status codes and provides structured error responses:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### Common Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | validation_error | Invalid request data |
| 401 | unauthorized | Authentication required |
| 403 | forbidden | Insufficient permissions |
| 404 | not_found | Resource not found |
| 409 | conflict | Resource conflict |
| 422 | unprocessable_entity | Valid data but unable to process |
| 429 | too_many_requests | Rate limit exceeded |
| 500 | server_error | Internal server error |

## API Endpoints

### Authentication

#### POST /auth/login
Authenticate a user and receive a JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### POST /auth/refresh
Refresh an expired token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### POST /auth/logout
Invalidate the current token.

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### Users

#### GET /users/me
Get current user profile.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "status": "active",
  "role": "user",
  "created_at": "2023-01-15T08:30:00Z",
  "updated_at": "2023-02-20T10:15:00Z"
}
```

#### PUT /users/me
Update current user profile.

**Request:**
```json
{
  "name": "John Smith",
  "email": "john.smith@example.com"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "john.smith@example.com",
  "name": "John Smith",
  "status": "active",
  "role": "user",
  "created_at": "2023-01-15T08:30:00Z",
  "updated_at": "2023-03-05T14:20:00Z"
}
```

### Deals

#### GET /deals
List all deals with pagination and filtering.

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)
- `status`: Filter by status (e.g., "active", "completed")
- `market_type`: Filter by market type (e.g., "stock", "crypto")
- `sort`: Sort field (e.g., "created_at", "price")
- `order`: Sort order ("asc" or "desc")

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "user_id": "456e4567-e89b-12d3-a456-426614174000",
      "title": "AAPL Stock Purchase",
      "description": "Apple stock purchase opportunity",
      "status": "active",
      "market_type": "stock",
      "price": 150.25,
      "target_price": 170.00,
      "quantity": 10,
      "created_at": "2023-02-15T09:30:00Z",
      "updated_at": "2023-02-15T09:30:00Z"
    },
    // More deals...
  ],
  "meta": {
    "total": 42,
    "page": 1,
    "limit": 10,
    "pages": 5
  }
}
```

#### POST /deals
Create a new deal.

**Request:**
```json
{
  "title": "BTC Purchase",
  "description": "Bitcoin purchase opportunity",
  "market_type": "crypto",
  "price": 30000.00,
  "target_price": 35000.00,
  "quantity": 0.5
}
```

**Response:**
```json
{
  "id": "789e4567-e89b-12d3-a456-426614174000",
  "user_id": "456e4567-e89b-12d3-a456-426614174000",
  "title": "BTC Purchase",
  "description": "Bitcoin purchase opportunity",
  "status": "active",
  "market_type": "crypto",
  "price": 30000.00,
  "target_price": 35000.00,
  "quantity": 0.5,
  "created_at": "2023-03-10T11:45:00Z",
  "updated_at": "2023-03-10T11:45:00Z"
}
```

#### GET /deals/{id}
Get a specific deal by ID.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "456e4567-e89b-12d3-a456-426614174000",
  "title": "AAPL Stock Purchase",
  "description": "Apple stock purchase opportunity",
  "status": "active",
  "market_type": "stock",
  "price": 150.25,
  "target_price": 170.00,
  "quantity": 10,
  "created_at": "2023-02-15T09:30:00Z",
  "updated_at": "2023-02-15T09:30:00Z",
  "scores": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174001",
      "score_type": "risk",
      "value": 65,
      "confidence": 80,
      "created_at": "2023-02-15T09:35:00Z"
    },
    {
      "id": "123e4567-e89b-12d3-a456-426614174002",
      "score_type": "profit_potential",
      "value": 75,
      "confidence": 70,
      "created_at": "2023-02-15T09:35:00Z"
    }
  ],
  "activities": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174003",
      "activity_type": "created",
      "description": "Deal created",
      "created_at": "2023-02-15T09:30:00Z"
    }
  ]
}
```

#### PUT /deals/{id}
Update a specific deal.

**Request:**
```json
{
  "title": "Updated AAPL Stock Purchase",
  "target_price": 180.00
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "456e4567-e89b-12d3-a456-426614174000",
  "title": "Updated AAPL Stock Purchase",
  "description": "Apple stock purchase opportunity",
  "status": "active",
  "market_type": "stock",
  "price": 150.25,
  "target_price": 180.00,
  "quantity": 10,
  "created_at": "2023-02-15T09:30:00Z",
  "updated_at": "2023-03-20T14:10:00Z"
}
```

#### DELETE /deals/{id}
Delete a specific deal.

**Response:**
```json
{
  "message": "Deal successfully deleted"
}
```

### Goals

#### GET /deals/{dealId}/goals
List all goals for a specific deal.

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "deal_id": "456e4567-e89b-12d3-a456-426614174000",
      "title": "Research Market Trends",
      "description": "Analyze current market trends for this stock",
      "status": "completed",
      "priority": 1,
      "due_date": "2023-03-01T00:00:00Z",
      "created_at": "2023-02-15T09:30:00Z",
      "updated_at": "2023-02-28T15:45:00Z"
    },
    // More goals...
  ],
  "meta": {
    "total": 3,
    "page": 1,
    "limit": 10,
    "pages": 1
  }
}
```

#### POST /deals/{dealId}/goals
Create a new goal for a specific deal.

**Request:**
```json
{
  "title": "Analyze Competitor Performance",
  "description": "Research how competitors are performing",
  "priority": 2,
  "due_date": "2023-04-15T00:00:00Z"
}
```

**Response:**
```json
{
  "id": "789e4567-e89b-12d3-a456-426614174000",
  "deal_id": "456e4567-e89b-12d3-a456-426614174000",
  "title": "Analyze Competitor Performance",
  "description": "Research how competitors are performing",
  "status": "pending",
  "priority": 2,
  "due_date": "2023-04-15T00:00:00Z",
  "created_at": "2023-03-20T10:15:00Z",
  "updated_at": "2023-03-20T10:15:00Z"
}
```

### Tasks

#### GET /goals/{goalId}/tasks
List all tasks for a specific goal.

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "goal_id": "456e4567-e89b-12d3-a456-426614174000",
      "agent_id": "789e4567-e89b-12d3-a456-426614174000",
      "title": "Collect Market Data",
      "description": "Gather recent market data for analysis",
      "status": "completed",
      "priority": 1,
      "due_date": "2023-02-25T00:00:00Z",
      "created_at": "2023-02-15T09:35:00Z",
      "updated_at": "2023-02-20T14:30:00Z"
    },
    // More tasks...
  ],
  "meta": {
    "total": 5,
    "page": 1,
    "limit": 10,
    "pages": 1
  }
}
```

#### POST /goals/{goalId}/tasks
Create a new task for a specific goal.

**Request:**
```json
{
  "title": "Analyze Quarterly Reports",
  "description": "Review latest quarterly financial reports",
  "agent_id": "789e4567-e89b-12d3-a456-426614174000",
  "priority": 2,
  "due_date": "2023-03-10T00:00:00Z"
}
```

**Response:**
```json
{
  "id": "789e4567-e89b-12d3-a456-426614174001",
  "goal_id": "456e4567-e89b-12d3-a456-426614174000",
  "agent_id": "789e4567-e89b-12d3-a456-426614174000",
  "title": "Analyze Quarterly Reports",
  "description": "Review latest quarterly financial reports",
  "status": "pending",
  "priority": 2,
  "due_date": "2023-03-10T00:00:00Z",
  "created_at": "2023-03-01T09:15:00Z",
  "updated_at": "2023-03-01T09:15:00Z"
}
```

### Agents

#### GET /agents
List all available agents.

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Market Analyst",
      "type": "market_analyst",
      "status": "active",
      "capabilities": ["market_research", "data_analysis", "trend_prediction"],
      "created_at": "2023-01-01T00:00:00Z",
      "updated_at": "2023-01-01T00:00:00Z"
    },
    // More agents...
  ],
  "meta": {
    "total": 4,
    "page": 1,
    "limit": 10,
    "pages": 1
  }
}
```

#### GET /agents/{id}
Get a specific agent.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Market Analyst",
  "type": "market_analyst",
  "status": "active",
  "capabilities": ["market_research", "data_analysis", "trend_prediction"],
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "config": {
    "analysis_depth": "deep",
    "data_sources": ["financial_news", "company_reports", "market_data"],
    "response_format": "structured"
  }
}
```

### Token Balance

#### GET /tokens/balance
Get current user's token balance.

**Response:**
```json
{
  "balances": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "token_type": "usage",
      "balance": 950,
      "created_at": "2023-01-15T08:30:00Z",
      "updated_at": "2023-03-01T10:15:00Z"
    },
    {
      "id": "123e4567-e89b-12d3-a456-426614174001",
      "token_type": "api",
      "balance": 5000,
      "created_at": "2023-01-15T08:30:00Z",
      "updated_at": "2023-02-15T14:25:00Z"
    }
  ]
}
```

#### GET /tokens/transactions
Get token transaction history.

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)
- `token_type`: Filter by token type (e.g., "usage", "api")
- `transaction_type`: Filter by transaction type (e.g., "purchase", "usage")

**Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "balance_id": "456e4567-e89b-12d3-a456-426614174000",
      "amount": -50,
      "transaction_type": "usage",
      "reference_id": "789e4567-e89b-12d3-a456-426614174000",
      "reference_type": "deal",
      "created_at": "2023-03-01T10:15:00Z"
    },
    // More transactions...
  ],
  "meta": {
    "total": 25,
    "page": 1,
    "limit": 10,
    "pages": 3
  }
}
```

#### POST /tokens/purchase
Purchase tokens.

**Request:**
```json
{
  "token_type": "usage",
  "amount": 1000,
  "payment_method": "credit_card",
  "payment_details": {
    "card_token": "tok_visa"
  }
}
```

**Response:**
```json
{
  "transaction": {
    "id": "123e4567-e89b-12d3-a456-426614174002",
    "balance_id": "456e4567-e89b-12d3-a456-426614174000",
    "amount": 1000,
    "transaction_type": "purchase",
    "created_at": "2023-03-15T09:30:00Z"
  },
  "new_balance": 1950
}
```

### Health Checks

#### GET /health
Check API health status.

**Response:**
```json
{
  "status": "ok",
  "version": "1.2.3",
  "timestamp": "2023-03-20T12:30:45Z",
  "services": {
    "database": "ok",
    "redis": "ok",
    "external_apis": "ok"
  }
}
```

#### GET /health/database
Check database health.

**Response:**
```json
{
  "status": "ok",
  "response_time_ms": 15,
  "connections": {
    "active": 5,
    "idle": 15,
    "max": 50
  }
}
```

#### GET /health/redis
Check Redis health.

**Response:**
```json
{
  "status": "ok",
  "response_time_ms": 8,
  "memory": {
    "used": "2.5 MB",
    "peak": "3.2 MB",
    "total": "50 MB"
  }
}
```

## Pagination

All list endpoints support pagination using the following parameters:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)

Response includes a `meta` object with pagination information:
```json
"meta": {
  "total": 42,    // Total number of items
  "page": 1,      // Current page
  "limit": 10,    // Items per page
  "pages": 5      // Total number of pages
}
```

## Filtering and Sorting

List endpoints support filtering and sorting using query parameters:
- Filtering: `field=value` (e.g., `status=active`)
- Sorting: `sort=field&order=asc` or `sort=field&order=desc`

Multiple filters can be combined (logical AND).

## API Versioning

The API uses URL versioning to ensure backward compatibility:
- Current version: `/v1/`
- Future versions: `/v2/`, `/v3/`, etc.

When a new version is released, the previous version will remain available for a deprecation period (typically 6 months). 