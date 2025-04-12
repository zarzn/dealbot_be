# Security Best Practices

## Overview

This document outlines the security best practices for the AI Agentic Deals System. It provides comprehensive guidance on security measures implemented throughout the system to protect user data, ensure system integrity, and maintain compliance with relevant regulations.

## Security Principles

Our approach to security is guided by these core principles:

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimal access rights for users and services
3. **Secure by Default**: Security enabled in default configurations
4. **Data Protection**: Strong safeguards for sensitive information
5. **Continuous Monitoring**: Proactive detection of security events
6. **Regular Testing**: Ongoing validation of security controls
7. **Security as Code**: Security integrated into development lifecycle

## Authentication and Authorization

### Authentication Best Practices

1. **JWT Implementation**
   - Short-lived access tokens (15 minutes)
   - Longer-lived refresh tokens (7 days) with rotation
   - Token signatures using RS256 algorithm (asymmetric)
   - Payload validation to prevent injection attacks

2. **Password Security**
   - Argon2id for password hashing
   - Password strength requirements:
     - Minimum 10 characters
     - Mix of uppercase, lowercase, numbers, and special characters
     - Password breach detection
   - Rate limiting for authentication attempts (5 attempts per minute)

3. **Multi-Factor Authentication**
   - Time-based one-time passwords (TOTP)
   - SMS verification as backup (with SIM-swap protections)
   - Security key support (WebAuthn/FIDO2)

### Authorization Best Practices

1. **Role-Based Access Control (RBAC)**
   - Defined roles: Admin, User, Support, ReadOnly
   - Fine-grained permission system
   - Resource-level access controls

2. **API Authorization**
   - Validate JWT on every request
   - Check permissions against endpoint requirements
   - Contextual authorization checks for data operations

3. **Token Validation and Revocation**
   - Signature validation on every request
   - Redis-based token blacklist for revoked tokens
   - Automatic revocation of compromised tokens

4. **Implementation Example**:

```python
# core/services/auth.py
async def validate_token_and_permissions(token: str, required_permissions: List[str]) -> Dict[str, Any]:
    """
    Validate token and check permissions.
    
    Args:
        token: The JWT token
        required_permissions: List of permissions required for the operation
        
    Returns:
        The token payload if valid
        
    Raises:
        AuthenticationError: If token is invalid or expired
        AuthorizationError: If user lacks required permissions
    """
    try:
        # Verify token signature and expiry
        payload = await verify_token(token)
        
        # Check if token is blacklisted
        if await is_token_blacklisted(token):
            raise AuthenticationError("Token has been revoked")
        
        # Extract user permissions
        user_permissions = payload.get("permissions", [])
        
        # Check if user has all required permissions
        if not all(perm in user_permissions for perm in required_permissions):
            logger.warning(
                "Permission denied",
                extra={
                    "user_id": payload.get("sub"),
                    "required_permissions": required_permissions,
                    "user_permissions": user_permissions
                }
            )
            raise AuthorizationError("You don't have permission to perform this action")
            
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")
```

## Data Protection and Privacy

### Data Security

1. **Data Classification**
   - Level 1: Public data (public deals, categories)
   - Level 2: Internal data (aggregated stats, non-PII metrics)
   - Level 3: Confidential data (user profiles, preferences)
   - Level 4: Restricted data (authentication, payment info)

2. **Encryption**
   - Data in transit: TLS 1.3 for all communications
   - Data at rest: AES-256 for database and backups
   - Field-level encryption for sensitive data (PII, payment)
   - Database column-level encryption for Level 4 data

3. **Database Security**
   - PostgreSQL with role-based access control
   - Database connection encryption
   - Query parameterization to prevent SQL injection
   - Database auditing for sensitive operations

4. **Example: Field-level Encryption**:

```python
# core/utils/encryption.py
from cryptography.fernet import Fernet
from core.config import settings

class FieldEncryption:
    """Utility for field-level encryption and decryption."""
    
    def __init__(self):
        self.fernet = Fernet(settings.DB_ENCRYPTION_KEY)
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string value."""
        if not data:
            return data
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, data: str) -> str:
        """Decrypt an encrypted string value."""
        if not data:
            return data
        return self.fernet.decrypt(data.encode()).decode()
```

### Privacy Controls

1. **User Data Management**
   - Self-service data export (GDPR Article 20)
   - Account deletion with complete data purge
   - Granular privacy settings

2. **Data Minimization**
   - Collection of only necessary data
   - Automatic data anonymization where possible
   - Regular data purging according to retention policies

3. **Consent Management**
   - Explicit consent collection and tracking
   - Purpose-specific consent options
   - Consent history and withdrawal support

4. **Example: Data Deletion Process**:

```python
# core/services/user/user_service.py
@transaction()
async def delete_user_account(user_id: UUID) -> None:
    """
    Delete user account and all associated data.
    
    This follows GDPR requirements for the right to be forgotten.
    """
    # Get user data
    user = await User.get(id=user_id)
    if not user:
        raise ResourceNotFoundError("User not found")
    
    # Log deletion request for compliance
    logger.info(
        "User deletion initiated",
        extra={"user_id": str(user_id)}
    )
    
    # Delete related data in correct order
    await TokenTransaction.delete_all(user_id=user_id)
    await UserTokenBalance.delete(user_id=user_id)
    await SavedDeal.delete_all(user_id=user_id)
    await UserGoal.delete_all(user_id=user_id)
    await UserPreference.delete(user_id=user_id)
    
    # Anonymize first, then delete the user
    await user.anonymize()
    await user.delete()
    
    # Log completion for audit trail
    logger.info(
        "User deletion completed successfully",
        extra={"user_id": str(user_id)}
    )
```

## API Security

### API Protection Mechanisms

1. **Rate Limiting**
   - Global rate limits (1000 requests per IP per hour)
   - Endpoint-specific limits (sensitive operations: 10 per minute)
   - User-based limits tied to subscription tier
   - Automatic blocking after threshold violations

2. **Input Validation**
   - Request schema validation using Pydantic
   - Content type validation
   - Parameter sanitization
   - Maximum request size limits

3. **Output Filtering**
   - Response data filtering based on user permissions
   - Prevention of sensitive data leakage
   - Structured error responses without system details

4. **Example: Rate Limiting Implementation**:

```python
# core/api/middleware/rate_limiter.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from core.services.redis import get_redis_service
from core.exceptions.base import RateLimitError
from core.utils.logger import logger

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for certain paths
        if self._should_skip_rate_limiting(request.url.path):
            return await call_next(request)
            
        # Determine rate limit key (IP-based or user-based)
        limit_key = await self._get_rate_limit_key(request)
        
        # Apply rate limiting
        redis = await get_redis_service()
        current_count = await redis.incr(limit_key)
        
        # Set expiry if this is the first request in the window
        if current_count == 1:
            await redis.expire(limit_key, 3600)  # 1 hour window
        
        # Get limit for this endpoint/user
        rate_limit = await self._get_rate_limit(request)
        
        # Check if rate limit exceeded
        if current_count > rate_limit:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "key": limit_key,
                    "limit": rate_limit,
                    "count": current_count,
                    "path": request.url.path
                }
            )
            
            # Calculate retry-after time
            ttl = await redis.ttl(limit_key)
            
            raise RateLimitError(
                message="Rate limit exceeded. Please try again later.",
                details={"limit": rate_limit, "current": current_count},
                retry_after=ttl
            )
            
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, rate_limit - current_count))
        
        return response
```

### Cross-Origin Resource Sharing (CORS)

1. **CORS Configuration**
   - Specific allowed origins (not wildcards)
   - Restricted HTTP methods
   - Limited allowed headers
   - Credentials access only for trusted origins

2. **Implementation Example**:

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.agentic-deals.com",
        "https://admin.agentic-deals.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "X-Request-ID"
    ],
    expose_headers=[
        "X-Request-ID", 
        "X-RateLimit-Limit", 
        "X-RateLimit-Remaining"
    ],
    max_age=86400,  # Cache preflight requests for 24 hours
)
```

## Infrastructure Security

### Cloud Security

1. **AWS Security Configuration**
   - VPC with public and private subnets
   - Security groups with minimal necessary access
   - Network ACLs for additional filtering
   - AWS WAF for web application protection

2. **IAM Best Practices**
   - Service-specific IAM roles with minimal permissions
   - IAM policies using least privilege principle
   - Regular key rotation
   - MFA for all IAM users

3. **Secrets Management**
   - AWS Secrets Manager for credentials
   - No hardcoded secrets in code or configuration
   - Automatic secret rotation
   - Encryption of all secrets at rest

### Container Security

1. **Docker Security**
   - Minimal base images (Alpine-based)
   - Regular security updates
   - Non-root container users
   - Read-only file systems where possible

2. **Example Dockerfile**:

```dockerfile
# Use specific version of lightweight base image
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set proper ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Network Security

1. **TLS Configuration**
   - TLS 1.3 only
   - Strong cipher suites
   - HSTS with long max-age
   - Certificate pinning for critical services

2. **API Gateway**
   - Input validation and sanitization
   - Request throttling
   - JWT validation at gateway level
   - DDoS protection

3. **Example: Nginx SSL Configuration**:

```nginx
server {
    listen 443 ssl http2;
    server_name api.agentic-deals.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/api.agentic-deals.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.agentic-deals.com/privkey.pem;
    
    # Modern TLS configuration
    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # Other security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; object-src 'none';" always;
    
    # Proxy to application
    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## AI-Specific Security Considerations

### LLM Security

1. **Prompt Injection Mitigation**
   - Input sanitization and validation
   - Context boundary enforcement
   - Detection of malicious prompts
   - Rate limiting on AI operations

2. **Output Filtering**
   - Content safety checks
   - PII detection and removal
   - Toxic content filtering
   - Hallucination mitigation through fact-checking

3. **Example: Secure LLM Processing**:

```python
# core/services/ai/security.py
from typing import Dict, List, Any
import re

class LLMSecurityService:
    """Service for securing LLM inputs and outputs."""
    
    def __init__(self):
        # Patterns for detecting potential prompt injections
        self.injection_patterns = [
            r"ignore previous instructions",
            r"disregard (?:all|previous) instructions",
            r"forget (?:all|your) training",
        ]
        self.injection_regex = re.compile("|".join(self.injection_patterns), re.IGNORECASE)
        
        # PII detection patterns
        self.pii_patterns = {
            "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
        }
        
    def validate_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Validate a prompt for security issues.
        
        Returns:
            Dict with 'is_safe' boolean and 'issues' list if any
        """
        issues = []
        
        # Check for potential prompt injections
        if self.injection_regex.search(prompt):
            issues.append({
                "type": "prompt_injection",
                "description": "Potential prompt injection detected"
            })
            
        # Check length to prevent token exhaustion attacks
        if len(prompt) > 10000:  # Adjust based on model context window
            issues.append({
                "type": "length_exceeded",
                "description": "Prompt exceeds maximum allowed length"
            })
        
        return {
            "is_safe": len(issues) == 0,
            "issues": issues
        }
    
    def sanitize_llm_output(self, output: str) -> Dict[str, Any]:
        """
        Sanitize LLM output to remove sensitive information.
        
        Returns:
            Dict with 'sanitized_output' and 'detected_pii' list
        """
        detected_pii = []
        sanitized = output
        
        # Check for and redact potential PII
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.finditer(pattern, sanitized)
            for match in matches:
                detected_pii.append({
                    "type": pii_type,
                    "position": match.span()
                })
                # Redact the PII
                sanitized = sanitized[:match.start()] + f"[REDACTED {pii_type}]" + sanitized[match.end():]
        
        return {
            "sanitized_output": sanitized,
            "detected_pii": detected_pii
        }
```

### Token System Security

1. **Token Transaction Security**
   - Atomic transaction processing
   - Defensive coding for balance operations
   - Complete audit trail of all token operations
   - Fraud detection for unusual patterns

2. **Balance Protection**
   - Double-entry accounting for token balances
   - Reconciliation checks to detect discrepancies
   - Transaction limits based on user tier
   - Circuit breakers for abnormal transaction volume

## Security Monitoring and Incident Response

### Logging and Monitoring

1. **Security Logging**
   - Authentication events
   - Authorization failures
   - Sensitive data access
   - Administrative actions
   - System configuration changes

2. **Log Format**:
   ```
   {
     "timestamp": "2023-07-15T10:30:45Z",
     "level": "WARNING",
     "event_type": "AUTHORIZATION_FAILURE",
     "message": "User attempted to access unauthorized resource",
     "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "resource": "/api/v1/admin/users",
     "ip_address": "198.51.100.234",
     "user_agent": "Mozilla/5.0...",
     "request_id": "req-1234567890"
   }
   ```

3. **Alerting Configuration**
   - Critical security alerts to on-call team
   - Graduated alerting based on severity
   - Alert aggregation to prevent alert fatigue
   - Automated response for common issues

### Incident Response

1. **Incident Response Process**
   - Detection and triage
   - Containment procedures
   - Investigation protocols
   - Remediation steps
   - Communication templates
   - Post-incident review

2. **Security Runbooks**
   - Account compromise response
   - Data breach handling
   - DDoS mitigation
   - Ransomware response
   - API abuse handling

## Security Testing

### Vulnerability Management

1. **Dependency Scanning**
   - Automated scanning in CI/CD pipeline
   - Weekly scheduled scans of all dependencies
   - Automatic creation of dependency update PRs
   - Critical vulnerability alerting

2. **Code Security Analysis**
   - Static Application Security Testing (SAST)
   - Dynamic Application Security Testing (DAST)
   - Software Composition Analysis (SCA)
   - AI-specific vulnerability scanning

3. **Example: GitHub Actions Security Workflow**:

```yaml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  dependency-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install safety bandit
      - name: Check for vulnerable dependencies
        run: safety check -r requirements.txt
      - name: Run Bandit security scan
        run: bandit -r ./backend -f json -o bandit-results.json
      - name: Upload results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: bandit-results.json

  sast-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run CodeQL Analysis
        uses: github/codeql-action/analyze@v2
        with:
          languages: python, javascript
```

### Penetration Testing

1. **Regular Testing Schedule**
   - Quarterly automated testing
   - Annual full penetration test
   - Post-major-release testing
   - Ad-hoc testing after significant changes

2. **Testing Focus Areas**
   - Authentication and session management
   - Access control mechanisms
   - Input validation and output encoding
   - API security
   - AI component security
   - Token system integrity

## Compliance

### Regulatory Compliance

1. **GDPR Compliance**
   - Data subject rights implementation
   - Lawful basis for processing
   - Privacy by design
   - Impact assessments

2. **PCI DSS Considerations**
   - Token system versus payment card data
   - Scope limitation
   - Security controls

3. **SOC 2 Controls**
   - Security control implementation
   - Documentation and evidence collection
   - Regular assessment and reporting

## References

1. [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
2. [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
3. [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)
4. [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
5. [Auth0 JWT Handbook](https://auth0.com/resources/ebooks/jwt-handbook)
6. [Backend Architecture Documentation](../architecture/architecture.md)
7. [Token System Architecture](../token/architecture.md) 