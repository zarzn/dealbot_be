# API Documentation

This directory contains documentation for all API endpoints and interfaces in the AI Agentic Deals System.

## API Types

The system provides multiple API types for different use cases:

1. [**REST API**](rest_api/README.md) - Standard HTTP-based API for most operations
2. [**WebSocket API**](websocket_api/README.md) - Real-time bidirectional communication
3. [**GraphQL API**](graphql/README.md) - Flexible query API for complex data operations (if implemented)

## REST API

The REST API provides standard HTTP endpoints for operations such as:

- Authentication and user management
- Deal search and retrieval
- AI analysis requests
- Token management

For detailed information, see the [REST API documentation](rest_api/README.md).

## WebSocket API

The WebSocket API enables real-time communication for:

- Live deal updates
- Notifications
- Chat functionality
- Real-time AI analysis results

For detailed documentation, see:
- [WebSocket Implementation Guide](websocket_api/implementation_guide.md)
- [WebSocket Quick Reference](websocket_api/quick_reference.md)
- [WebSocket Client Guide](websocket_api/client_guide.md)
- [WebSocket Server Guide](websocket_api/server_guide.md)

## Authentication

All APIs use the same authentication mechanism:

1. Obtain a JWT token via `/api/auth/login` endpoint
2. Include the token:
   - For REST API: In the `Authorization` header as `Bearer {token}`
   - For WebSocket API: As a query parameter `?token={token}`

## Rate Limiting

Rate limits apply to all API types:

| API Type | Default Rate Limit |
|----------|-------------------|
| REST API | 200 requests/minute |
| WebSocket | 20 messages/minute |
| GraphQL | 100 requests/minute |

## API Versioning

API versioning follows this scheme:

- REST API: `/api/v1/resource`
- WebSocket: Version specified in connection message
- GraphQL: Schema versioning with deprecation notices

## Error Handling

All APIs follow consistent error reporting:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": { 
    // Additional error context if available
  }
}
```

For WebSocket-specific error formats, see the [WebSocket Quick Reference](websocket_api/quick_reference.md).

## Common Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Resource created |
| 400 | Bad request (client error) |
| 401 | Unauthorized (authentication required) |
| 403 | Forbidden (permission denied) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Server error |

## API Documentation Generation

API documentation is generated using:

1. OpenAPI 3.0 schema for REST APIs
2. Custom documentation for WebSocket APIs

## Testing the APIs

- REST API: Use the Swagger UI at `/docs` when running the development server
- WebSocket API: Use the `wscat` tool as described in the [WebSocket Testing Guide](websocket_api/server_guide.md#testing-websocket-api) 