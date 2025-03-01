# Authentication & Authorization

## Overview
The AI Agentic Deals System implements a robust security system using JWT tokens, role-based access control, and secure session management. All authentication and token management code is centralized in the `backend/core/services/auth.py` module.

## Authentication Service

### Location
```
backend/core/services/auth.py
```

### Responsibilities
- User authentication
- Token generation and validation
- Token blacklisting
- Token balance management
- OAuth2 configuration
- Session management

## Token Management

### JWT Configuration
```python
JWT_SETTINGS = {
    "algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "token_type": "bearer"
}
```

### Token Types
1. **Access Token**
   - Short-lived (30 minutes)
   - Used for API access
   - Contains user claims

2. **Refresh Token**
   - Long-lived (7 days)
   - Used to obtain new access tokens
   - Rotated on use

### Token Format
```json
{
    "sub": "user_id",
    "exp": 1234567890,
    "iat": 1234567890,
    "type": "access",
    "scope": "full",
    "jti": "unique_token_id"
}
```

## Security Implementation

### Password Hashing
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

### Token Generation
```python
async def create_access_token(user_id: UUID) -> str:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    data = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + expires_delta,
        "type": "access",
        "jti": str(uuid4())
    }
    return jwt.encode(data, settings.JWT_SECRET, algorithm=JWT_SETTINGS["algorithm"])
```

### Token Validation
```python
async def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[JWT_SETTINGS["algorithm"]]
        )
        if await is_token_blacklisted(payload["jti"]):
            raise InvalidTokenError("Token is blacklisted")
        return payload
    except JWTError:
        raise InvalidTokenError("Invalid token")
```

## Authentication Flow

### 1. User Registration
```python
async def register_user(user_data: UserCreate) -> User:
    # Validate email uniqueness
    if await get_user_by_email(user_data.email):
        raise UserExistsError("Email already registered")
    
    # Create user with hashed password
    user_data.password = get_password_hash(user_data.password)
    user = await create_user(user_data)
    
    # Send verification email
    await send_verification_email(user)
    
    return user
```

### 2. User Login
```python
async def login_user(email: str, password: str) -> TokenResponse:
    # Verify user credentials
    user = await authenticate_user(email, password)
    if not user:
        raise InvalidCredentialsError()
    
    # Generate tokens
    access_token = await create_access_token(user.id)
    refresh_token = await create_refresh_token(user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
```

### 3. Token Refresh
```python
async def refresh_access_token(refresh_token: str) -> TokenResponse:
    # Verify refresh token
    payload = await verify_token(refresh_token)
    if payload["type"] != "refresh":
        raise InvalidTokenError("Not a refresh token")
    
    # Blacklist used refresh token
    await blacklist_token(payload["jti"])
    
    # Generate new tokens
    user_id = UUID(payload["sub"])
    new_access_token = await create_access_token(user_id)
    new_refresh_token = await create_refresh_token(user_id)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )
```

## Token Blacklist Management

### Redis Implementation
```python
async def blacklist_token(token_id: str) -> None:
    """Add token to blacklist with expiration."""
    redis = await get_redis_client()
    await redis.setex(
        f"blacklist:{token_id}",
        settings.TOKEN_BLACKLIST_TTL,
        "1"
    )

async def is_token_blacklisted(token_id: str) -> bool:
    """Check if token is blacklisted."""
    redis = await get_redis_client()
    return await redis.exists(f"blacklist:{token_id}")
```

## Session Management

### Session Storage
- Use Redis for session storage
- Session TTL: 24 hours
- Secure session ID generation
- Session data encryption

### Session Operations
```python
async def create_session(user_id: UUID, data: dict) -> str:
    session_id = generate_secure_session_id()
    await store_session(session_id, user_id, data)
    return session_id

async def get_session(session_id: str) -> Optional[dict]:
    return await retrieve_session(session_id)

async def invalidate_session(session_id: str) -> None:
    await delete_session(session_id)
```

## Security Middleware

### 1. Authentication Middleware
```python
async def authenticate_request(request: Request) -> Optional[User]:
    token = extract_token_from_header(request)
    if not token:
        return None
    
    try:
        payload = await verify_token(token)
        user = await get_user_by_id(UUID(payload["sub"]))
        return user
    except (InvalidTokenError, UserNotFoundError):
        return None
```

### 2. Rate Limiting Middleware
```python
async def rate_limit_middleware(request: Request):
    client_ip = request.client.host
    endpoint = request.url.path
    
    if await is_rate_limited(client_ip, endpoint):
        raise RateLimitExceededError()
```

## Security Best Practices

### 1. Password Requirements
- Minimum length: 8 characters
- Must contain: uppercase, lowercase, number, special character
- Password history: prevent reuse of last 5 passwords
- Maximum age: 90 days

### 2. Rate Limiting
- Standard endpoints: 100 requests/minute
- Authentication endpoints: 10 requests/minute
- Token operations: 50 requests/minute
- IP-based and user-based limits

### 3. Input Validation
- Validate all input parameters
- Sanitize user input
- Prevent SQL injection
- Validate file uploads

### 4. Error Handling
- Don't expose sensitive information
- Log security events
- Implement proper error responses
- Monitor failed attempts

## Monitoring and Logging

### Security Events
- Failed login attempts
- Token invalidations
- Rate limit violations
- Suspicious activities

### Audit Logging
```python
async def log_security_event(
    event_type: str,
    user_id: Optional[UUID],
    details: dict
) -> None:
    await create_audit_log(
        event_type=event_type,
        user_id=user_id,
        details=details,
        ip_address=request.client.host,
        timestamp=datetime.utcnow()
    )
```

## Security Headers

### HTTP Security Headers
```python
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}
```

## Error Responses

### Authentication Errors
```json
{
    "status": "error",
    "error": {
        "code": "AUTH_001",
        "message": "Authentication failed",
        "details": {
            "reason": "Invalid credentials"
        }
    }
}
```

### Token Errors
```json
{
    "status": "error",
    "error": {
        "code": "TOKEN_001",
        "message": "Invalid token",
        "details": {
            "reason": "Token has expired"
        }
    }
}
```

## Security Testing

### Test Cases
1. Authentication flows
2. Token validation
3. Password policies
4. Rate limiting
5. Input validation
6. Error handling
7. Session management

### Security Scans
- Regular vulnerability scans
- Dependency checks
- Code security analysis
- Penetration testing 