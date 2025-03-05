# REST API Documentation

This document provides information about the REST API endpoints available in the AI Agentic Deals System.

## API Overview

The REST API is the primary interface for interacting with the AI Agentic Deals System programmatically. It provides endpoints for user management, deal operations, AI analysis, and system configuration.

## Base URL

- Development: `http://localhost:8000/api`
- Production: `https://api.agentic-deals.example.com/api`

## Authentication

All API requests (except for login/registration) require authentication:

1. Obtain a JWT token by calling the login endpoint
2. Include the token in the `Authorization` header as `Bearer {token}`

Example:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Available Endpoints

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate user and receive JWT token |
| `/api/auth/register` | POST | Register new user account |
| `/api/auth/refresh` | POST | Refresh JWT token |
| `/api/auth/logout` | POST | Invalidate current token |

### User Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/users/me` | GET | Get current user profile |
| `/api/users/me` | PUT | Update current user profile |
| `/api/users/{id}` | GET | Get user by ID (admin only) |
| `/api/users` | GET | List users (admin only) |

### Deals

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/deals` | GET | List all deals (with filtering) |
| `/api/deals` | POST | Create new deal |
| `/api/deals/{id}` | GET | Get deal by ID |
| `/api/deals/{id}` | PUT | Update deal |
| `/api/deals/{id}` | DELETE | Delete deal |
| `/api/deals/{id}/analyze` | POST | Run AI analysis on deal |

### Markets

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/markets` | GET | List available markets |
| `/api/markets/{id}` | GET | Get market details |
| `/api/markets/{id}/deals` | GET | Get deals in specific market |

### AI Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/deal/{id}` | GET | Get analysis results for deal |
| `/api/analysis/request` | POST | Request new analysis |
| `/api/analysis/models` | GET | List available AI models |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/status` | GET | Check system status |
| `/api/system/metrics` | GET | Get system metrics (admin only) |

## Request & Response Format

### Request Format

All requests with a body should use JSON format:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Response Format

All responses follow a standard format:

```json
{
  "status": "success",
  "data": {
    // Response data here
  },
  "meta": {
    // Pagination, counts, etc.
  }
}
```

Or for errors:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    // Additional error context
  }
}
```

## Pagination

List endpoints support pagination with these query parameters:

- `page`: Page number (1-based)
- `limit`: Items per page (default: 20, max: 100)

Example: `/api/deals?page=2&limit=50`

Response includes pagination metadata:

```json
{
  "status": "success",
  "data": [...],
  "meta": {
    "page": 2,
    "limit": 50,
    "total": 327,
    "pages": 7
  }
}
```

## Filtering & Sorting

Most list endpoints support filtering and sorting:

- Filtering: `field=value` or `field[operator]=value`
- Sorting: `sort=field` or `sort=-field` (descending)

Example: `/api/deals?status=active&price[gte]=1000&sort=-created_at`

Supported operators:
- `eq`: Equal (default)
- `ne`: Not equal
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `like`: Contains substring (for text fields)

## Rate Limiting

The API enforces rate limits to prevent abuse:

- 200 requests per minute per user
- 50 requests per minute for unauthenticated endpoints

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Requests allowed per window
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Time (in seconds) until window resets

## Versioning

The API uses URL versioning:

```
/api/v1/resource
```

The current stable version is v1.

## Interactive Documentation

When running in development mode, interactive API documentation is available at:

```
http://localhost:8000/docs
```

This Swagger UI allows you to explore and test all endpoints.

## SDK Clients

Official SDK clients are available for:

- JavaScript/TypeScript: `@agentic-deals/js-client`
- Python: `agentic-deals-client`

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2023-05-01 | Initial stable release |
| v0.9.0 | 2023-04-15 | Beta release with core functionality |

## Further Reading

- [Error Code Reference](error_codes.md)
- [Authentication Guide](authentication.md)
- [WebSocket API Documentation](../websocket_api/README.md) for real-time updates 