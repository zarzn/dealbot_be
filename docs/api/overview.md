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