# Authentication Guide

This guide explains the authentication mechanisms used in the AI Agentic Deals System.

## Authentication Flow

The system uses JWT (JSON Web Tokens) for authentication. The authentication flow works as follows:

1. User provides credentials (email/password)
2. Server validates credentials and returns a JWT token pair (access token and refresh token)
3. Client includes the access token in subsequent API requests
4. When the access token expires, client uses the refresh token to get a new token pair
5. User can explicitly logout to invalidate tokens

## Token Types

The system uses two types of tokens:

1. **Access Token**
   - Short-lived (15 minutes)
   - Used for API authentication
   - Contains user identity and permissions

2. **Refresh Token**
   - Longer-lived (7 days)
   - Used only to obtain new token pairs
   - Stored securely and managed via HTTP-only cookies for web clients

## Authentication Endpoints

### Login

**Endpoint:** `POST /api/auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "user_id",
      "email": "user@example.com",
      "name": "User Name",
      "role": "user"
    }
  }
}
```

### Register

**Endpoint:** `POST /api/auth/register`

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure_password",
  "name": "New User",
  "company": "Company Name"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "new_user_id",
      "email": "newuser@example.com",
      "name": "New User",
      "role": "user"
    }
  }
}
```

### Refresh Token

**Endpoint:** `POST /api/auth/refresh`

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Alternatively, the refresh token can be sent in an HTTP-only cookie for web clients.

**Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

### Logout

**Endpoint:** `POST /api/auth/logout`

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Request Body:** (empty)

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": "Successfully logged out"
  }
}
```

## Using Tokens in API Requests

### HTTP Header

Include the access token in the `Authorization` header for all API requests:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### JavaScript Example

```javascript
async function fetchUserProfile() {
  const response = await fetch('https://api.agentic-deals.example.com/api/users/me', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      'Content-Type': 'application/json'
    }
  });
  
  return await response.json();
}
```

### Python Example

```python
import requests

def fetch_user_profile(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(
        'https://api.agentic-deals.example.com/api/users/me',
        headers=headers
    )
    
    return response.json()
```

## Token Management Best Practices

### Web Applications

1. Store the access token in memory (e.g., JavaScript variable)
2. Store the refresh token in an HTTP-only cookie
3. Implement automatic token refresh when access token expires
4. Clear tokens on logout

Example token refresh handling:

```javascript
// Intercept API requests
axios.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;
    
    // If error is due to expired token and we haven't tried refreshing yet
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        // Call refresh endpoint
        const refreshResponse = await axios.post('/api/auth/refresh');
        const { access_token } = refreshResponse.data.data;
        
        // Update token in storage
        localStorage.setItem('access_token', access_token);
        
        // Update authorization header
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
        
        // Retry the original request
        return axios(originalRequest);
      } catch (refreshError) {
        // If refresh fails, redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);
```

### Mobile Applications

1. Store tokens in secure storage (e.g., Keychain for iOS, EncryptedSharedPreferences for Android)
2. Implement biometric authentication (when available) for added security
3. Clear tokens on logout or when security is compromised

### Server-to-Server Applications

1. Use client credentials flow for authentication
2. Store client ID and secret securely (e.g., environment variables, secret management service)
3. Implement token caching to avoid frequent authentication requests

## Error Handling

Common authentication errors:

1. **Invalid Credentials** (`AUTH_INVALID_CREDENTIALS`)
   - Status code: 401
   - Solution: Verify email and password

2. **Expired Token** (`AUTH_EXPIRED_TOKEN`)
   - Status code: 401
   - Solution: Refresh the token using refresh endpoint

3. **Invalid Token** (`AUTH_INVALID_TOKEN`)
   - Status code: 401
   - Solution: Re-authenticate user

4. **Insufficient Permissions** (`AUTH_INSUFFICIENT_PERMISSIONS`)
   - Status code: 403
   - Solution: Verify user has necessary permissions or upgrade account

5. **Rate Limiting** (`AUTH_LOGIN_ATTEMPT_LIMIT`)
   - Status code: 429
   - Solution: Wait before retrying or implement exponential backoff

## Security Considerations

1. **HTTPS Only**
   - All authentication requests must be over HTTPS
   - Production API rejects non-HTTPS requests

2. **Token Storage**
   - Never store tokens in localStorage for production web applications
   - Use HTTP-only cookies for refresh tokens
   - Consider using secure in-memory solutions for access tokens

3. **Token Validation**
   - Validate token signatures on the server
   - Check token expiration
   - Verify token audience and issuer

4. **Token Revocation**
   - Implement token blacklisting for security-sensitive operations
   - Allow users to revoke all sessions

5. **Account Protection**
   - Implement rate limiting for login attempts
   - Support two-factor authentication for sensitive operations
   - Notify users of suspicious login attempts

## Testing Authentication

Use the following test accounts in the development environment:

| Email | Password | Role |
|-------|----------|------|
| `test@example.com` | `password123` | User |
| `admin@example.com` | `password123` | Admin |

**Note:** These accounts only work in the development environment.

## Additional Resources

- [JWT.io](https://jwt.io/) - Debugger and information about JWTs
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [WebSocket API Authentication](../websocket_api/implementation_guide.md#authentication) - For WebSocket authentication 