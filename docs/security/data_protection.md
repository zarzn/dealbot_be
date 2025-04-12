# Data Protection

## Overview

The AI Agentic Deals System implements comprehensive data protection measures to safeguard user information, deal data, and system integrity. This document outlines the technical strategies, policies, and implementation details for data protection throughout the system.

## Data Classification

### Classification Levels

The system classifies data into the following protection categories:

1. **Public Data** (Level 0)
   - Public deal information
   - General system documentation
   - Marketing materials

2. **Internal Data** (Level 1)
   - Aggregated statistics
   - Non-sensitive user preferences
   - Non-personally identifiable analytics  

3. **Sensitive Data** (Level 2)
   - User account information
   - Shopping patterns and preferences
   - Deal interaction history
   - Payment information references

4. **Highly Sensitive Data** (Level 3)
   - Authentication credentials
   - API keys and secrets
   - Token balances
   - Personal identifiable information (PII)

## Encryption Strategy

### Data at Rest

1. **Database Encryption**
   - Transparent data encryption (TDE) for PostgreSQL
   - Encrypted backup files
   - Secure key management through AWS KMS

```python
# Database encryption configuration
DATABASE_ENCRYPTION = {
    "enabled": True,
    "key_provider": "aws_kms",
    "kms_key_id": "alias/agentic-deals-db-key",
    "region": "us-east-1",
    "auto_rotation": True,
    "rotation_period_days": 90
}
```

2. **Sensitive Field Encryption**
   - Field-level encryption for PII and sensitive data
   - Different encryption keys for different data categories
   - Key rotation policies

```python
# Example of field-level encryption implementation
class EncryptedField(TypeDecorator):
    impl = String
    
    def __init__(self, key_id="default", **kwargs):
        self.key_id = key_id
        super().__init__(**kwargs)
    
    def process_bind_parameter(self, value, dialect):
        if value is not None:
            encryption_service = get_encryption_service()
            return encryption_service.encrypt(value, self.key_id)
        return None
    
    def process_result_value(self, value, dialect):
        if value is not None:
            encryption_service = get_encryption_service()
            return encryption_service.decrypt(value, self.key_id)
        return None
```

### Data in Transit

1. **TLS Configuration**
   - TLS 1.3 required for all connections
   - Strong cipher suites
   - Perfect forward secrecy
   - HSTS implementation

2. **API Security**
   - Encrypted request/response bodies
   - Secure header policies
   - Certificate pinning for critical operations

```python
# FastAPI TLS middleware configuration
app.add_middleware(
    HTTPSRedirectMiddleware,
    enabled=settings.ENVIRONMENT != "development"
)

app.add_middleware(
    SecurityHeadersMiddleware,
    content_security_policy={
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline'",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https://storage.example.com",
        "connect-src": "'self' https://api.example.com"
    },
    strict_transport_security={
        "max-age": 31536000,
        "includeSubDomains": True
    }
)
```

### Encryption Implementation

The `EncryptionService` handles all encryption/decryption operations:

```python
class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self):
        self.kms_client = boto3.client('kms', region_name=settings.AWS_REGION)
        self.cache = TTLCache(maxsize=100, ttl=3600)  # Cache for key retrieval
    
    async def encrypt(self, plaintext: str, key_id: str = "default") -> str:
        """
        Encrypt plaintext using the specified key.
        
        Args:
            plaintext: Text to encrypt
            key_id: Identifier for the encryption key
            
        Returns:
            Encrypted data in base64 format
        """
        if not plaintext:
            return plaintext
            
        # Get encryption key
        key = await self._get_encryption_key(key_id)
        
        # Generate a random IV
        iv = os.urandom(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Encrypt data
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV and encrypted data
        result = iv + encrypted_data
        
        # Return as base64
        return base64.b64encode(result).decode('utf-8')
    
    async def decrypt(self, ciphertext: str, key_id: str = "default") -> str:
        """
        Decrypt ciphertext using the specified key.
        
        Args:
            ciphertext: Base64-encoded encrypted data
            key_id: Identifier for the encryption key
            
        Returns:
            Decrypted text
        """
        if not ciphertext:
            return ciphertext
            
        # Get encryption key
        key = await self._get_encryption_key(key_id)
        
        # Decode from base64
        raw_data = base64.b64decode(ciphertext)
        
        # Extract IV and ciphertext
        iv = raw_data[:16]
        encrypted_data = raw_data[16:]
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt data
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        
        # Return as string
        return data.decode('utf-8')
    
    async def _get_encryption_key(self, key_id: str) -> bytes:
        """Retrieve encryption key from KMS."""
        cache_key = f"encryption_key:{key_id}"
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        # Get data key from KMS
        response = self.kms_client.generate_data_key(
            KeyId=settings.KMS_KEY_IDS[key_id],
            KeySpec='AES_256'
        )
        
        # Cache the plaintext key
        key = response['Plaintext']
        self.cache[cache_key] = key
        
        return key
```

## Data Anonymization and Pseudonymization

### Anonymization Techniques

1. **Data Masking**
   - Partial masking for display (e.g., "j****@example.com")
   - Full field masking for sensitive data
   - Context-aware masking based on user permissions

2. **Aggregation**
   - Aggregate data for analytics to remove individual identifiers
   - K-anonymity for user groups
   - Differential privacy for statistical queries

### Pseudonymization Implementation

```python
class PseudonymizationService:
    """Service for pseudonymizing user data for analytics."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.hash_key = settings.PSEUDONYMIZATION_KEY
    
    async def pseudonymize_user_id(self, user_id: UUID) -> str:
        """Convert a user ID to a pseudonymous identifier."""
        # Create deterministic but non-reversible identifier
        hash_input = f"{user_id}:{self.hash_key}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    async def pseudonymize_email(self, email: str) -> str:
        """Convert an email to a pseudonymous value."""
        if not email:
            return ""
            
        # Extract domain for analytics
        parts = email.split('@')
        if len(parts) != 2:
            return self.pseudonymize_value(email)
            
        domain = parts[1]
        pseudonymized_local = self.pseudonymize_value(parts[0])
        
        # Return pseudonymized local part with real domain for analytics
        return f"{pseudonymized_local}@{domain}"
    
    async def pseudonymize_value(self, value: str) -> str:
        """Convert an arbitrary value to a pseudonymous value."""
        if not value:
            return ""
            
        hash_input = f"{value}:{self.hash_key}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    async def prepare_analytics_data(self, user_data: dict) -> dict:
        """Prepare user data for analytics by pseudonymizing PII."""
        result = user_data.copy()
        
        # Pseudonymize identifiers
        if 'id' in result:
            result['id'] = await self.pseudonymize_user_id(result['id'])
        
        if 'email' in result:
            result['email'] = await self.pseudonymize_email(result['email'])
        
        if 'name' in result:
            result['name'] = await self.pseudonymize_value(result['name'])
        
        # Remove other sensitive fields
        for field in ['phone', 'address', 'payment_info']:
            if field in result:
                del result[field]
        
        return result
```

## Access Control

### Role-Based Access Control (RBAC)

1. **User Roles**
   - Anonymous
   - Standard User
   - Premium User
   - Administrator
   - System Administrator

2. **Permission Sets**
   - Data read permissions
   - Data write permissions
   - Administrative permissions
   - System configuration permissions

### Implementation

The `PermissionService` enforces access control:

```python
class PermissionService:
    """Service for managing and checking permissions."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def check_permission(self, user_id: UUID, permission: str, resource_id: Optional[UUID] = None) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user_id: The user ID to check
            permission: The permission to check
            resource_id: Optional resource ID for resource-specific permissions
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Get user with roles
        stmt = (
            select(User)
            .options(joinedload(User.roles))
            .where(User.id == user_id)
        )
        
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        # Check for superadmin
        if any(role.name == 'superadmin' for role in user.roles):
            return True
        
        # Check permission in roles
        role_has_permission = False
        for role in user.roles:
            if permission in role.permissions:
                role_has_permission = True
                break
        
        if not role_has_permission:
            return False
        
        # If resource-specific, check resource permissions
        if resource_id:
            # Check resource ownership or specific resource permissions
            return await self._check_resource_permission(user_id, permission, resource_id)
        
        return True
    
    async def _check_resource_permission(self, user_id: UUID, permission: str, resource_id: UUID) -> bool:
        """Check resource-specific permissions."""
        # Implementation depends on resource type
        # Check for ownership or explicit resource permissions
        return False  # Default to deny
```

## Data Retention and Deletion

### Retention Policies

1. **Active Data**
   - User profile data: Until account deletion
   - Deal data: 2 years after discovery
   - Transaction history: 7 years

2. **Archived Data**
   - Archived after retention period
   - Access restricted to authorized personnel
   - Automatic purging after extended retention period

3. **Log Data**
   - System logs: 90 days
   - Authentication logs: 1 year
   - Audit logs: 7 years

### Implementation

The system implements an automated data lifecycle manager:

```python
class DataLifecycleManager:
    """Manages data retention and deletion according to policies."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def process_retention_policies(self):
        """Process all retention policies."""
        await self._process_user_data_retention()
        await self._process_deal_data_retention()
        await self._process_transaction_data_retention()
        await self._process_log_data_retention()
    
    async def _process_user_data_retention(self):
        """Process user data retention policies."""
        # Archive inactive users
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        stmt = (
            select(User)
            .where(User.last_login < cutoff_date)
            .where(User.status == 'active')
        )
        
        result = await self.db.execute(stmt)
        inactive_users = result.scalars().all()
        
        for user in inactive_users:
            await self._archive_user_data(user)
    
    async def _archive_user_data(self, user: User):
        """Archive user data."""
        # Create archive record
        archive = UserDataArchive(
            user_id=user.id,
            email=user.email,
            data=user.to_dict(),
            archived_at=datetime.utcnow()
        )
        
        self.db.add(archive)
        
        # Update user status
        user.status = 'archived'
        user.archived_at = datetime.utcnow()
        
        await self.db.commit()
    
    async def permanently_delete_user_data(self, user_id: UUID, hard_delete: bool = False):
        """
        Permanently delete user data.
        
        Args:
            user_id: The user ID to delete
            hard_delete: If True, physically delete records; if False, mark as deleted
        """
        if hard_delete:
            # Physical deletion (GDPR right to be forgotten)
            await self._hard_delete_user_data(user_id)
        else:
            # Logical deletion (standard account closure)
            await self._soft_delete_user_data(user_id)
            
        # Record deletion in audit log
        await self._log_data_deletion(user_id, "user_data", hard_delete)
```

## Right to Access and Portability

### Data Export

1. **User Data Export**
   - Complete profile data
   - Activity history
   - Preferences and settings

2. **Export Formats**
   - JSON (machine-readable)
   - PDF (human-readable)
   - CSV (spreadsheet-compatible)

### Implementation

The `DataPortabilityService` handles user data exports:

```python
class DataPortabilityService:
    """Service for providing users with their data (GDPR compliance)."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.file_service = FileService()
    
    async def generate_data_export(self, user_id: UUID, format: str = "json") -> str:
        """
        Generate a complete export of user data.
        
        Args:
            user_id: The user requesting their data
            format: Export format (json, pdf, csv)
            
        Returns:
            URL to download the export file
        """
        # Collect all user data
        user_data = await self._collect_user_data(user_id)
        
        # Generate file in requested format
        if format == "json":
            file_data = self._generate_json_export(user_data)
            filename = f"user_data_export_{user_id}.json"
        elif format == "pdf":
            file_data = await self._generate_pdf_export(user_data)
            filename = f"user_data_export_{user_id}.pdf"
        elif format == "csv":
            file_data = self._generate_csv_export(user_data)
            filename = f"user_data_export_{user_id}.csv"
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        # Store file and generate download URL
        file_id = await self.file_service.store_file(file_data, filename)
        download_url = await self.file_service.get_download_url(file_id, expires_in=3600)
        
        # Log the data export
        await self._log_data_export(user_id, format)
        
        return download_url
    
    async def _collect_user_data(self, user_id: UUID) -> dict:
        """Collect all data associated with a user."""
        # Get user profile
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Build comprehensive data structure
        user_data = {
            "profile": user.to_dict(exclude=["password_hash"]),
            "preferences": await self._get_user_preferences(user_id),
            "deals": await self._get_user_deals(user_id),
            "collections": await self._get_user_collections(user_id),
            "comments": await self._get_user_comments(user_id),
            "activities": await self._get_user_activities(user_id),
            "tokens": await self._get_token_balance(user_id)
        }
        
        return user_data
```

## Auditing and Monitoring

### Audit Logging

1. **Logged Actions**
   - Authentication events
   - Data access events
   - Data modification events
   - Administrative actions

2. **Log Content**
   - User identifier
   - Action timestamp
   - Action type
   - Resource affected
   - Source IP/device information
   - Success/failure status

### Implementation

The `AuditService` handles comprehensive audit logging:

```python
class AuditService:
    """Service for audit logging and monitoring."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def log_auth_event(self, user_id: Optional[UUID], event_type: str, success: bool, details: dict = None):
        """Log an authentication-related event."""
        await self._create_audit_log(
            user_id=user_id,
            resource_type="authentication",
            resource_id=None,
            action=event_type,
            success=success,
            details=details
        )
    
    async def log_data_access(self, user_id: UUID, resource_type: str, resource_id: UUID, details: dict = None):
        """Log a data access event."""
        await self._create_audit_log(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="access",
            success=True,
            details=details
        )
    
    async def log_data_modification(self, user_id: UUID, resource_type: str, resource_id: UUID, action: str, details: dict = None):
        """Log a data modification event."""
        await self._create_audit_log(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            success=True,
            details=details
        )
    
    async def _create_audit_log(self, user_id: Optional[UUID], resource_type: str, resource_id: Optional[UUID], action: str, success: bool, details: dict = None):
        """Create an audit log entry."""
        # Create log entry
        log_entry = AuditLog(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            success=success,
            ip_address=self._get_client_ip(),
            user_agent=self._get_user_agent(),
            details=details or {},
            created_at=datetime.utcnow()
        )
        
        self.db.add(log_entry)
        await self.db.commit()
    
    def _get_client_ip(self):
        """Get client IP from request context."""
        # Implementation depends on web framework
        return "127.0.0.1"  # Placeholder
    
    def _get_user_agent(self):
        """Get user agent from request context."""
        # Implementation depends on web framework
        return "Unknown"  # Placeholder
```

## Data Breach Response

### Detection Mechanisms

1. **Anomaly Detection**
   - Unusual access patterns
   - Volume-based anomalies
   - Time-based anomalies
   - Location-based anomalies

2. **Intrusion Detection**
   - Network-level monitoring
   - Application-level monitoring
   - Database query monitoring

### Response Plan

1. **Containment**
   - Isolate affected systems
   - Revoke compromised credentials
   - Block suspicious IP addresses

2. **Investigation**
   - Forensic analysis
   - Scope determination
   - Vulnerability identification

3. **Notification**
   - User notification procedures
   - Regulatory notification requirements
   - Documentation and reporting

## Compliance Framework

### GDPR Compliance

1. **User Rights Support**
   - Right to access
   - Right to rectification
   - Right to erasure
   - Right to restrict processing
   - Right to data portability
   - Right to object

2. **Data Processing Records**
   - Purpose of processing
   - Categories of data
   - Data transfer information
   - Security measures

### CCPA Compliance

1. **User Rights Support**
   - Right to know
   - Right to delete
   - Right to opt-out
   - Right to non-discrimination

2. **Service Provider Requirements**
   - Contract provisions
   - Use limitations
   - Security requirements

## Data Protection Best Practices

1. **Code-Level Practices**
   - Input validation for all data entry points
   - Output encoding for all data presentation
   - Parameterized queries for database access
   - Strict type checking

2. **Infrastructure Practices**
   - Network segmentation
   - Least privilege access
   - Regular security updates
   - Backup and recovery testing

3. **Operational Practices**
   - Security training for developers
   - Regular security reviews
   - Penetration testing
   - Bug bounty program

## Testing Requirements

### Security Testing

1. **Static Analysis**
   - Code scanning for security issues
   - Dependency scanning
   - Infrastructure as code scanning

2. **Dynamic Analysis**
   - Interactive application security testing
   - API security testing
   - Database security testing

3. **Manual Testing**
   - Penetration testing
   - Security code reviews
   - Security design reviews

### Data Protection Testing

1. **Encryption Testing**
   - Encryption algorithm validation
   - Key management testing
   - Encryption performance testing

2. **Access Control Testing**
   - Permission boundary testing
   - Role separation testing
   - Privilege escalation testing

3. **Data Lifecycle Testing**
   - Retention policy enforcement testing
   - Deletion verification
   - Archiving and retrieval testing 