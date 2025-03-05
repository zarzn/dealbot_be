# Error Code Reference

This document provides a comprehensive list of error codes that may be returned by the AI Agentic Deals System API.

## Error Response Format

All API errors follow this standard format:

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

## Authentication Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTH_INVALID_CREDENTIALS` | 401 | The provided credentials are invalid |
| `AUTH_EXPIRED_TOKEN` | 401 | The authentication token has expired |
| `AUTH_INVALID_TOKEN` | 401 | The authentication token is invalid or malformed |
| `AUTH_MISSING_TOKEN` | 401 | No authentication token was provided |
| `AUTH_INSUFFICIENT_PERMISSIONS` | 403 | The authenticated user lacks required permissions |
| `AUTH_USER_INACTIVE` | 403 | The user account is inactive or suspended |
| `AUTH_LOGIN_ATTEMPT_LIMIT` | 429 | Too many failed login attempts |

## Resource Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `RESOURCE_NOT_FOUND` | 404 | The requested resource does not exist |
| `RESOURCE_ALREADY_EXISTS` | 409 | A resource with the same identifier already exists |
| `RESOURCE_CONFLICT` | 409 | The request conflicts with the current state of the resource |
| `RESOURCE_GONE` | 410 | The resource previously existed but is no longer available |

## Validation Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | The request data failed validation |
| `VALIDATION_MISSING_FIELD` | 400 | A required field is missing from the request |
| `VALIDATION_INVALID_FORMAT` | 400 | A field has an invalid format or type |
| `VALIDATION_INVALID_OPTION` | 400 | A field value is not one of the allowed options |
| `VALIDATION_OUT_OF_RANGE` | 400 | A numeric field is outside the allowed range |

## Deal-specific Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `DEAL_INVALID_STATUS` | 400 | The deal status transition is invalid |
| `DEAL_EXPIRED` | 400 | The deal has expired and cannot be modified |
| `DEAL_LOCKED` | 403 | The deal is locked for editing by another user |
| `DEAL_ANALYSIS_IN_PROGRESS` | 409 | An analysis is already in progress for this deal |
| `DEAL_INSUFFICIENT_DATA` | 422 | The deal lacks required data for the requested operation |

## AI Analysis Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ANALYSIS_LIMIT_EXCEEDED` | 429 | The user has exceeded their analysis quota |
| `ANALYSIS_FAILED` | 500 | The analysis operation failed |
| `ANALYSIS_INVALID_MODEL` | 400 | The requested AI model is invalid or unavailable |
| `ANALYSIS_TIMEOUT` | 504 | The analysis operation timed out |

## Server Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `SERVER_ERROR` | 500 | An unexpected server error occurred |
| `SERVER_MAINTENANCE` | 503 | The server is in maintenance mode |
| `SERVER_OVERLOADED` | 503 | The server is currently overloaded |
| `SERVER_TIMEOUT` | 504 | A dependent service timed out |
| `DATABASE_ERROR` | 500 | A database error occurred |

## Rate Limiting Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `RATE_LIMIT_EXCEEDED` | 429 | The client has sent too many requests |
| `QUOTA_EXCEEDED` | 429 | The user has exceeded their usage quota |

## Integration Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INTEGRATION_ERROR` | 500 | An error occurred with an external service |
| `INTEGRATION_UNAVAILABLE` | 503 | An external service is currently unavailable |
| `INTEGRATION_INVALID_RESPONSE` | 502 | An external service returned an invalid response |

## File-related Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `FILE_TOO_LARGE` | 413 | The uploaded file exceeds the size limit |
| `FILE_INVALID_TYPE` | 415 | The file type is not supported |
| `FILE_CORRUPT` | 400 | The file is corrupt or invalid |
| `FILE_STORAGE_ERROR` | 500 | An error occurred while storing the file |

## Handling Errors

Clients should handle errors as follows:

1. Check the `status` field to determine if the response indicates an error
2. Use the `code` field to programmatically handle specific error cases
3. Display the `message` field to users when appropriate
4. Use the `details` field for additional context or field-specific errors

Example error handling in JavaScript:

```javascript
async function callApi(endpoint) {
  try {
    const response = await fetch(endpoint);
    const data = await response.json();
    
    if (data.status === 'error') {
      switch (data.code) {
        case 'AUTH_EXPIRED_TOKEN':
          // Refresh token or redirect to login
          return refreshTokenAndRetry(endpoint);
          
        case 'RESOURCE_NOT_FOUND':
          // Show not found message
          showNotification(`The requested resource was not found: ${data.message}`);
          break;
          
        case 'VALIDATION_ERROR':
          // Show field-specific errors
          showFormErrors(data.details.fields);
          break;
          
        default:
          // Generic error handling
          showErrorMessage(data.message);
      }
      return null;
    }
    
    return data.data; // Return actual response data
  } catch (err) {
    // Network or parsing error
    showErrorMessage('A network error occurred. Please try again.');
    return null;
  }
}
```

## HTTP Status Codes

For reference, the API uses these standard HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource was successfully created |
| 204 | No Content - Request succeeded but no response body |
| 400 | Bad Request - Client error, invalid request format |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Authenticated but insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Request conflicts with current state |
| 422 | Unprocessable Entity - Semantic errors in request |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Unexpected server error |
| 503 | Service Unavailable - Server temporarily unavailable |

## Reporting Errors

If you encounter unexpected errors or have questions about specific error codes, please contact our support team at support@agentic-deals.example.com with:

1. The complete error response (code, message, and details)
2. The API endpoint you were trying to access
3. Timestamp of the error
4. Any additional context that might help us diagnose the issue 