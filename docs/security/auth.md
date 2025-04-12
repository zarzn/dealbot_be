# Authentication and Security

## Overview

This document outlines the authentication and security mechanisms implemented in the AI Agentic Deals System. It covers user authentication, authorization, token management, data protection, and security best practices enforced throughout the system.

## Authentication System

### Authentication Flow

1. **User Registration**
   - Users register with email and password
   - Passwords are hashed using Argon2id with appropriate work factors
   - Email verification is required to activate accounts

2. **Login Process**
   - User submits credentials through secure endpoint
   - System validates credentials against stored hash
   - JWT tokens (access and refresh) are issued upon successful authentication
   - Failed attempts are logged and rate-limited

3. **Token-Based Authentication**
   - **Access Token**: Short-lived (15 minutes), used for API requests
   - **Refresh Token**: Longer-lived (7 days), used to obtain new access tokens
   - All tokens are cryptographically signed with RS256 algorithm
   - Claims include user ID, scope, and expiration

### Authentication Service

The `AuthService` class in `core/services/auth.py` manages all authentication-related functionality:

```python
class AuthService:
    """Authentication service handling user auth and token management."""
    
    async def authenticate_user(self, email: str, password: str) -> User:
        """Authenticate a user with email and password."""
        
    async def create_tokens(self, user_id: str) -> TokenPair:
        """Create access and refresh tokens for a user."""
        
    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Create a new token pair using a refresh token."""
        
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding it to the blacklist."""
        
    async def verify_token(self, token: str, token_type: TokenType) -> dict:
        """Verify a token's validity and return its payload."""
```

### Token Lifecycle Management

1. **Token Generation**
   - Generated using `jose` library with RSA keys (2048-bit)
   - Access tokens include user permissions and roles
   - Rotation of signing keys scheduled quarterly

2. **Token Storage and Management**
   - Active tokens tracked in Redis with TTL matching token expiration
   - Token revocation implemented via blacklist in Redis
   - Blacklist entries automatically expire after token would have expired

3. **Token Refresh Strategy**
   - Sliding window approach with automatic refresh when expiration approaches
   - Absolute maximum lifetime enforced (30 days)
   - Device fingerprinting used to detect anomalous refresh attempts

## Authorization System

### Role-Based Access Control (RBAC)

The system implements RBAC with the following roles:

1. **Anonymous**: Unauthenticated users with minimal access
2. **User**: Standard authenticated users
3. **Premium**: Users with premium subscription
4. **Admin**: System administrators with access to management features
5. **System**: Internal service-to-service communication

Roles are defined in the `core/models/enums.py` file:

```python
class UserRole(str, Enum):
    """User role enum."""
    
    ANONYMOUS = "anonymous"
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"
    SYSTEM = "system"
```

### Permission System

Permissions are granular and composable:

```python
class Permission(str, Enum):
    """Permission enum for access control."""
    
    # Deal permissions
    DEALS_READ = "deals:read"
    DEALS_CREATE = "deals:create"
    DEALS_UPDATE = "deals:update"
    DEALS_DELETE = "deals:delete"
    
    # User permissions
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    
    # Admin permissions
    ADMIN_ACCESS = "admin:access"
    ADMIN_USERS = "admin:users"
    ADMIN_DEALS = "admin:deals"
    
    # Token permissions
    TOKENS_READ = "tokens:read"
    TOKENS_TRANSFER = "tokens:transfer"
    TOKENS_ADMIN = "tokens:admin"
```

### Role-Permission Mapping

Roles are mapped to permissions in the `core/services/auth.py` file:

```python
ROLE_PERMISSIONS = {
    UserRole.ANONYMOUS: {
        Permission.DEALS_READ
    },
    UserRole.USER: {
        Permission.DEALS_READ,
        Permission.DEALS_CREATE,
        Permission.USERS_READ,
        Permission.TOKENS_READ,
        Permission.TOKENS_TRANSFER
    },
    UserRole.PREMIUM: {
        Permission.DEALS_READ,
        Permission.DEALS_CREATE,
        Permission.DEALS_UPDATE,
        Permission.USERS_READ,
        Permission.TOKENS_READ,
        Permission.TOKENS_TRANSFER
    },
    UserRole.ADMIN: {
        Permission.DEALS_READ,
        Permission.DEALS_CREATE,
        Permission.DEALS_UPDATE,
        Permission.DEALS_DELETE,
        Permission.USERS_READ,
        Permission.USERS_CREATE,
        Permission.USERS_UPDATE,
        Permission.ADMIN_ACCESS,
        Permission.ADMIN_USERS,
        Permission.ADMIN_DEALS,
        Permission.TOKENS_READ,
        Permission.TOKENS_TRANSFER,
        Permission.TOKENS_ADMIN
    }
}
```

### Authorization Implementation

Authorization is enforced at two levels:

1. **API Level**: Through FastAPI dependencies
2. **Service Level**: Through explicit permission checks

#### API Level Authorization

```python
# core/api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.services.auth import get_auth_service
from core.models.enums import Permission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get the current user from a token."""
    auth_service = get_auth_service()
    try:
        payload = await auth_service.verify_token(token, TokenType.ACCESS)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def require_permission(
    permission: Permission,
    current_user: dict = Depends(get_current_user)
):
    """Check if the current user has the required permission."""
    user_permissions = current_user.get("permissions", [])
    if permission not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
```

#### Usage in API Endpoints

```python
# core/api/endpoints/deals.py
from fastapi import APIRouter, Depends

from core.api.dependencies import get_current_user, require_permission
from core.models.enums import Permission

router = APIRouter()

@router.get("/deals/")
async def get_deals(current_user: dict = Depends(get_current_user)):
    """Get all deals. Available to all authenticated users."""
    # Implementation...

@router.post("/deals/")
async def create_deal(
    deal: DealCreate,
    _: None = Depends(require_permission(Permission.DEALS_CREATE))
):
    """Create a new deal. Requires DEALS_CREATE permission."""
    # Implementation...

@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: str,
    _: None = Depends(require_permission(Permission.DEALS_DELETE))
):
    """Delete a deal. Requires DEALS_DELETE permission."""
    # Implementation...
```

## Data Protection

### Data Encryption

1. **Data at Rest**
   - Database encryption using PostgreSQL's encryption features
   - Sensitive fields encrypted using `cryptography` library (AES-256-GCM)
   - Encryption keys stored in AWS KMS, rotated quarterly

2. **Data in Transit**
   - All communications secured via TLS 1.3
   - HTTP Strict Transport Security (HSTS) enabled
   - Certificate pinning implemented in mobile clients

### Personally Identifiable Information (PII) Handling

1. **PII Minimization**
   - Only essential PII collected
   - Data retention periods enforced
   - User consent required for all data collection

2. **PII Storage and Access**
   - PII stored in encrypted format
   - Access to PII logged and audited
   - Field-level encryption for highly sensitive data

### Implementation Examples

```python
# core/utils/encryption.py
from cryptography.fernet import Fernet
from core.config import settings

def get_encryption_key():
    """Get encryption key from AWS KMS or settings."""
    # Implementation fetches the key from KMS or settings

def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data with Fernet (AES-128-CBC)."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data with Fernet (AES-128-CBC)."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode()).decode()
```

## API Security

### Request Validation

1. **Input Validation**
   - Schema-based validation using Pydantic
   - Type checking and constraint enforcement
   - Custom validators for business rules

2. **Request Sanitization**
   - HTML sanitization for user-generated content
   - XSS protection through context-aware escaping
   - SQLi prevention through parameterized queries

### Rate Limiting and Throttling

1. **Rate Limiting Strategy**
   - IP-based rate limiting
   - User-based rate limiting
   - Endpoint-specific limits

2. **Implementation**
   - Redis-based sliding window counter
   - Gradual backoff for repeated violations
   - Clear rate limit headers in responses

```python
# core/api/middleware/rate_limit.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from core.services.redis import get_redis_service
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis."""
    
    async def dispatch(self, request: Request, call_next):
        # Get client identifier (IP or user ID)
        client_id = self._get_client_id(request)
        
        # Calculate rate limit
        rate_limit_key = f"ratelimit:{client_id}:{request.scope['path']}"
        
        # Check if rate limit exceeded
        redis = get_redis_service()
        current = await redis.incr(rate_limit_key)
        
        # Set expiry if first request
        if current == 1:
            await redis.expire(rate_limit_key, 60)  # 60 second window
            
        # Set headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = str(max(0, 100 - current))
        
        # If exceeded, return 429
        if current > 100:
            return Response(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                media_type="application/json"
            )
            
        return response
```

## Cross-Site Request Forgery (CSRF) Protection

1. **CSRF Strategy**
   - Double Submit Cookie pattern
   - Same-Site cookie attribute set to Lax
   - Origin validation on state-changing requests

2. **Implementation in Frontend**
   - CSRF token included in all forms
   - Token validated on backend

## Security Best Practices

### Password Management

1. **Password Policy**
   - Minimum 12 characters with complexity requirements
   - Password breach detection via HaveIBeenPwned API
   - Maximum password age (90 days)
   - Password history enforcement (no reuse of last 5 passwords)

2. **Password Storage**
   - Argon2id with appropriate work factors
   - Salted hashes with unique per-user salt
   - Regular updates to work factors as hardware improves

```python
# core/utils/security.py
from passlib.context import CryptContext

# Configure password hashing
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)
```

### Account Security

1. **Account Recovery**
   - Secure account recovery process
   - Time-limited recovery tokens
   - Multi-channel verification

2. **Multi-Factor Authentication (MFA)**
   - TOTP-based MFA using Google Authenticator compatible algorithm
   - Recovery codes for backup access
   - Notification on MFA changes

3. **Session Management**
   - Session timeout after inactivity
   - Single session per user (optional)
   - Device tracking and abnormal login detection

## Monitoring and Detection

### Security Logging

1. **Authentication Events**
   - Login attempts (successful and failed)
   - Password changes
   - Account lockouts

2. **Authorization Events**
   - Access denied events
   - Permission changes
   - Privilege escalation

3. **System Events**
   - Configuration changes
   - Service starts/stops
   - Deployment events

### Audit Logs

Audit logs are collected for all security-relevant actions:

```python
# core/services/audit_log.py
from datetime import datetime
from core.models.enums import AuditAction
from core.database import get_db_session

async def log_audit_event(
    user_id: str,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    details: dict = None
):
    """Log an audit event to the database."""
    async with get_db_session() as session:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            timestamp=datetime.utcnow()
        )
        session.add(audit_log)
        await session.commit()
```

### Intrusion Detection

1. **Anomaly Detection**
   - User behavior analytics
   - Traffic pattern monitoring
   - Authentication anomalies

2. **Alerting**
   - Real-time alerts for suspicious activities
   - Escalation procedures
   - Incident response integration

## Secure Development Practices

### Security Testing

1. **Static Application Security Testing (SAST)**
   - Source code scanning with Bandit
   - Dependency vulnerability scanning
   - Regular security code reviews

2. **Dynamic Application Security Testing (DAST)**
   - Automated scanning with OWASP ZAP
   - Regular penetration testing
   - API security testing

3. **Security Regression Testing**
   - Security tests in CI/CD pipeline
   - Security issues tracked as bugs
   - No deployment with open security issues

### Dependency Management

1. **Dependency Policy**
   - Only approved packages
   - Regular dependency updates
   - Vulnerability monitoring and notification

2. **Implementation**
   - Automated dependency scanning
   - Dependency lock files committed
   - Security patches prioritized

## Incident Response

### Security Incident Process

1. **Detection**
   - Automated detection through monitoring
   - User-reported incidents
   - Third-party notifications

2. **Containment**
   - Account suspension
   - Token revocation
   - Network isolation

3. **Eradication**
   - Vulnerability patching
   - Malicious content removal
   - Compromised credential reset

4. **Recovery**
   - Service restoration
   - Data integrity verification
   - Communication with affected users

5. **Lessons Learned**
   - Incident documentation
   - Process improvement
   - Training updates

## Compliance

### Regulatory Compliance

1. **GDPR Compliance**
   - Data protection assessments
   - Privacy by design
   - Right to be forgotten implementation

2. **SOC 2 Compliance**
   - Security controls documentation
   - Regular security assessments
   - Continuous monitoring

### Compliance Implementation

1. **Data Deletion**
   - Complete user data removal on request
   - Audit trail of deletion requests
   - Data retention policy enforcement

2. **Data Export**
   - Complete user data export functionality
   - Machine-readable format
   - Secure delivery mechanism

## Reference Architecture

### Security Components

1. **Frontend Security**
   - CSP headers
   - XSS protection
   - CSRF tokens

2. **API Gateway Security**
   - WAF integration
   - Request validation
   - Rate limiting

3. **Application Security**
   - Authentication service
   - Authorization checks
   - Data encryption

4. **Database Security**
   - Encryption at rest
   - Access controls
   - Audit logging

## Appendix

### Security Configuration Examples

#### CORS Configuration

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://app.example.com",
    "https://api.example.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

#### Security Headers

```python
# core/api/middleware/security_headers.py
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'"
        
        return response

# Adding the middleware to the application
app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
```

### Security Checklists

#### Deployment Security Checklist

- [ ] All secrets stored in secure storage (AWS Secrets Manager)
- [ ] Debug mode disabled in production
- [ ] All unused ports and services disabled
- [ ] TLS certificates valid and up to date
- [ ] WAF rules reviewed and updated
- [ ] Security scanning performed pre-deployment
- [ ] Monitoring and alerting verified
- [ ] Backup/restore procedures verified

#### API Security Checklist

- [ ] Authentication required for protected endpoints
- [ ] Authorization checks on all secured resources
- [ ] Input validation on all parameters
- [ ] Rate limiting configured
- [ ] Response headers properly set
- [ ] Error messages don't leak sensitive info
- [ ] Sensitive data properly encrypted
- [ ] Audit logging enabled for sensitive operations 