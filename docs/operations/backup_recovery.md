# Backup and Recovery Procedures

## Overview

This document outlines the backup and recovery procedures for the AI Agentic Deals System. It defines the strategies, schedules, responsibilities, and procedures for ensuring data protection, business continuity, and disaster recovery. Proper implementation of these procedures is critical for maintaining system reliability and data integrity.

## Backup Strategy

The AI Agentic Deals System employs a comprehensive backup strategy that covers all critical data components:

1. **Database Backups**: PostgreSQL databases containing user data, deals, transactions, etc.
2. **Object Storage Backups**: S3 buckets containing static assets, user uploads, and exports
3. **Configuration Backups**: Infrastructure configuration, environment variables, and secrets
4. **Code Repository Backups**: Source code and deployment configurations

### Backup Types

| Backup Type | Description | Retention | Used For |
|-------------|-------------|-----------|----------|
| Full Backup | Complete copy of all data | 30 days | Complete system restoration |
| Incremental Backup | Changes since last backup | 7 days | Point-in-time recovery |
| Snapshot Backup | Storage-level backup | 14 days | Rapid recovery of entire volumes |
| Continuous Backup | Real-time replication | N/A | High availability and disaster recovery |

### Backup Schedule

| Component | Backup Type | Frequency | Retention | Storage Location |
|-----------|-------------|-----------|-----------|------------------|
| Production Database | Automated Snapshot | Daily at 01:00 UTC | 30 days | AWS S3 (backup bucket) |
| Production Database | Point-in-Time Recovery | Continuous (5-minute intervals) | 7 days | AWS RDS PITR |
| Production Database | Full Dump | Weekly (Sunday at 02:00 UTC) | 90 days | AWS S3 (encrypted backup bucket) |
| Staging Database | Automated Snapshot | Daily at 03:00 UTC | 7 days | AWS S3 (backup bucket) |
| S3 Buckets | Cross-Region Replication | Continuous | N/A | Secondary AWS Region |
| S3 Buckets | Versioning | Continuous | 90 days | AWS S3 |
| Configuration (SSM/Secrets) | Backup | Daily at 04:00 UTC | 30 days | AWS S3 (encrypted backup bucket) |
| Code Repository | Mirror | On each commit | Indefinite | Secondary Git repository |

## Automated Backup Procedures

### Database Backups

#### RDS Automated Snapshots

AWS RDS provides automated daily snapshots of the production and staging databases.

**Configuration**:
```bash
# View current backup settings
aws rds describe-db-instances \
    --db-instance-identifier agentic-deals-production \
    --query 'DBInstances[0].BackupRetentionPeriod' \
    --no-cli-pager

# Configure automated backup
aws rds modify-db-instance \
    --db-instance-identifier agentic-deals-production \
    --backup-retention-period 30 \
    --preferred-backup-window "01:00-02:00" \
    --apply-immediately \
    --no-cli-pager
```

#### Point-in-Time Recovery

AWS RDS automatically maintains transaction logs that enable point-in-time recovery for the previous 7 days (configured via backup retention period).

#### Manual Database Dumps

A weekly full database dump is performed to supplement the RDS snapshots.

**Backup Script** (`backend/scripts/ops/backup_database.ps1`):
```powershell
# Database full backup script
param (
    [string]$Environment = "production"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "agentic_deals_${Environment}_${timestamp}.sql.gz"

# Get DB credentials from AWS Secrets Manager
$secretName = "agentic-deals-${Environment}-db-credentials"
$secretJson = aws secretsmanager get-secret-value --secret-id $secretName --query SecretString --output text
$credentials = ConvertFrom-Json $secretJson

# Perform database dump
$env:PGPASSWORD = $credentials.password
pg_dump -h $credentials.host -U $credentials.username -d $credentials.dbname -F c | gzip > $backupFile

# Upload to S3
aws s3 cp $backupFile "s3://agentic-deals-backups/${Environment}/database/$backupFile" --no-cli-pager

# Remove local backup file
Remove-Item $backupFile

# Log backup completion
Write-Output "Database backup completed: $backupFile"
```

This script is executed weekly via AWS Systems Manager Maintenance Window.

### S3 Bucket Backups

#### Versioning

All production S3 buckets have versioning enabled to protect against accidental deletions and modifications.

**Configuration**:
```bash
# Enable versioning on a bucket
aws s3api put-bucket-versioning \
    --bucket agentic-deals-production-assets \
    --versioning-configuration Status=Enabled \
    --no-cli-pager
```

#### Cross-Region Replication

Critical production buckets are configured with cross-region replication for disaster recovery.

**Configuration**:
```bash
# Enable cross-region replication
aws s3api put-bucket-replication \
    --bucket agentic-deals-production-assets \
    --replication-configuration file://replication-config.json \
    --no-cli-pager
```

Content of `replication-config.json`:
```json
{
  "Role": "arn:aws:iam::ACCOUNT_ID:role/s3-replication-role",
  "Rules": [
    {
      "Status": "Enabled",
      "Priority": 1,
      "DeleteMarkerReplication": { "Status": "Enabled" },
      "Destination": {
        "Bucket": "arn:aws:s3:::agentic-deals-production-assets-dr",
        "StorageClass": "STANDARD"
      }
    }
  ]
}
```

### Configuration Backups

AWS SSM Parameters and Secrets Manager secrets are backed up daily.

**Backup Script** (`backend/scripts/ops/backup_configuration.ps1`):
```powershell
# Configuration backup script
param (
    [string]$Environment = "production"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "config_backup_${Environment}_${timestamp}"
New-Item -ItemType Directory -Force -Path $backupDir

# Backup SSM Parameters
$ssmParameters = aws ssm get-parameters-by-path --path "/agentic-deals/${Environment}/" --recursive --with-decryption --no-cli-pager
$ssmParameters | ConvertTo-Json -Depth 10 > "$backupDir/ssm_parameters.json"

# Backup Secrets (metadata only, not values for security)
$secrets = aws secretsmanager list-secrets --filter "Key=tag-key,Values=Environment" "Key=tag-value,Values=${Environment}" --no-cli-pager
$secrets | ConvertTo-Json -Depth 10 > "$backupDir/secrets_metadata.json"

# Compress backup directory
Compress-Archive -Path $backupDir -DestinationPath "${backupDir}.zip"

# Upload to S3
aws s3 cp "${backupDir}.zip" "s3://agentic-deals-backups/${Environment}/configuration/${backupDir}.zip" --no-cli-pager

# Remove local backup files
Remove-Item -Recurse -Force $backupDir
Remove-Item "${backupDir}.zip"

Write-Output "Configuration backup completed: ${backupDir}.zip"
```

### Code Repository Backups

The source code repository is mirrored to a secondary Git repository for redundancy.

**GitHub Actions Workflow** (`.github/workflows/repo-backup.yml`):
```yaml
name: Repository Backup

on:
  push:
    branches:
      - main
      - develop
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday at midnight UTC

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Push to backup repository
        run: |
          git config --global user.name 'GitHub Actions'
          git config --global user.email 'actions@github.com'
          git remote add backup https://${{ secrets.BACKUP_REPO_TOKEN }}@github.com/agentic-deals-backup/agentic-deals-system.git
          git push backup --all --force
          git push backup --tags --force
```

## Verification Procedures

All backups undergo automated verification to ensure their integrity and usability.

### Database Backup Verification

Database backups are verified monthly by restoring them to a test environment and running validation checks.

**Verification Script** (`backend/scripts/ops/verify_database_backup.ps1`):
```powershell
param (
    [string]$BackupFile,
    [string]$Environment = "production"
)

# Create a temporary database for verification
$tempDbName = "backup_verification_$(Get-Random)"

# Get DB credentials from AWS Secrets Manager
$secretName = "agentic-deals-${Environment}-db-credentials"
$secretJson = aws secretsmanager get-secret-value --secret-id $secretName --query SecretString --output text
$credentials = ConvertFrom-Json $secretJson

# Download backup from S3 if not local
if (-not (Test-Path $BackupFile)) {
    aws s3 cp $BackupFile . --no-cli-pager
    $BackupFile = Split-Path $BackupFile -Leaf
}

# Create temporary database
$env:PGPASSWORD = $credentials.password
psql -h $credentials.host -U $credentials.username -d postgres -c "CREATE DATABASE $tempDbName"

# Restore backup to temporary database
if ($BackupFile.EndsWith(".gz")) {
    gunzip -c $BackupFile | pg_restore -h $credentials.host -U $credentials.username -d $tempDbName
} else {
    pg_restore -h $credentials.host -U $credentials.username -d $tempDbName -f $BackupFile
}

# Run verification queries
$userCount = psql -h $credentials.host -U $credentials.username -d $tempDbName -t -c "SELECT COUNT(*) FROM users"
$dealCount = psql -h $credentials.host -U $credentials.username -d $tempDbName -t -c "SELECT COUNT(*) FROM deals"
$tokenCount = psql -h $credentials.host -U $credentials.username -d $tempDbName -t -c "SELECT COUNT(*) FROM token_transactions"

# Clean up
psql -h $credentials.host -U $credentials.username -d postgres -c "DROP DATABASE $tempDbName"

# Verify reasonable counts (adjust thresholds as needed)
$verification = $true
if ([int]$userCount -lt 10) { 
    Write-Output "Verification failed: User count too low ($userCount)"
    $verification = $false
}
if ([int]$dealCount -lt 100) { 
    Write-Output "Verification failed: Deal count too low ($dealCount)"
    $verification = $false
}
if ([int]$tokenCount -lt 100) { 
    Write-Output "Verification failed: Token transaction count too low ($tokenCount)"
    $verification = $false
}

if ($verification) {
    Write-Output "Backup verification successful: Users: $userCount, Deals: $dealCount, Transactions: $tokenCount"
    return 0
} else {
    Write-Output "Backup verification failed!"
    return 1
}
```

### Configuration Backup Verification

Configuration backups are verified by checking for the presence of critical parameters.

**Verification Script** (`backend/scripts/ops/verify_config_backup.ps1`):
```powershell
param (
    [string]$BackupFile,
    [string]$Environment = "production"
)

# Download backup from S3 if not local
if (-not (Test-Path $BackupFile)) {
    aws s3 cp $BackupFile . --no-cli-pager
    $BackupFile = Split-Path $BackupFile -Leaf
}

# Extract backup if it's a zip file
$extractDir = "config_verification_$(Get-Random)"
Expand-Archive -Path $BackupFile -DestinationPath $extractDir

# Check for critical parameters
$ssmFile = "$extractDir/ssm_parameters.json"
$ssmParams = Get-Content $ssmFile | ConvertFrom-Json

$requiredParams = @(
    "/agentic-deals/${Environment}/database/host",
    "/agentic-deals/${Environment}/api/url",
    "/agentic-deals/${Environment}/llm/provider"
)

$missing = @()
foreach ($param in $requiredParams) {
    $exists = $ssmParams.Parameters | Where-Object { $_.Name -eq $param }
    if (-not $exists) {
        $missing += $param
    }
}

# Clean up
Remove-Item -Recurse -Force $extractDir

if ($missing.Count -eq 0) {
    Write-Output "Configuration backup verification successful"
    return 0
} else {
    Write-Output "Configuration backup verification failed! Missing parameters: $($missing -join ', ')"
    return 1
}
```

## Recovery Procedures

### Database Recovery

#### From RDS Snapshot

```bash
# List available snapshots
aws rds describe-db-snapshots \
    --db-instance-identifier agentic-deals-production \
    --no-cli-pager

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier agentic-deals-production-restored \
    --db-snapshot-identifier rds:agentic-deals-production-2023-07-15-01-00 \
    --no-cli-pager
```

#### Point-in-Time Recovery

```bash
# Perform point-in-time recovery
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier agentic-deals-production \
    --target-db-instance-identifier agentic-deals-production-restored \
    --restore-time "2023-07-15T10:00:00Z" \
    --no-cli-pager
```

#### From Full Dump

**Recovery Script** (`backend/scripts/ops/restore_database.ps1`):
```powershell
param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$Environment = "production",
    [switch]$CreateNewDatabase = $false,
    [string]$TargetDatabase = ""
)

# Get DB credentials from AWS Secrets Manager
$secretName = "agentic-deals-${Environment}-db-credentials"
$secretJson = aws secretsmanager get-secret-value --secret-id $secretName --query SecretString --output text
$credentials = ConvertFrom-Json $secretJson

# Set target database name
if ([string]::IsNullOrEmpty($TargetDatabase)) {
    $TargetDatabase = $credentials.dbname
}

# Download backup from S3 if not local
if (-not (Test-Path $BackupFile)) {
    aws s3 cp $BackupFile . --no-cli-pager
    $BackupFile = Split-Path $BackupFile -Leaf
}

# Create new database if requested
if ($CreateNewDatabase) {
    $env:PGPASSWORD = $credentials.password
    psql -h $credentials.host -U $credentials.username -d postgres -c "CREATE DATABASE $TargetDatabase"
}

# Restore database from backup
if ($BackupFile.EndsWith(".gz")) {
    gunzip -c $BackupFile | pg_restore -h $credentials.host -U $credentials.username -d $TargetDatabase --clean --if-exists
} else {
    pg_restore -h $credentials.host -U $credentials.username -d $TargetDatabase -f $BackupFile --clean --if-exists
}

Write-Output "Database restore completed to: $TargetDatabase"
```

### S3 Data Recovery

#### Restore from Versioning

```bash
# List object versions
aws s3api list-object-versions \
    --bucket agentic-deals-production-assets \
    --prefix "path/to/object" \
    --no-cli-pager

# Restore specific version
aws s3api restore-object \
    --bucket agentic-deals-production-assets \
    --key "path/to/object" \
    --version-id "VERSION_ID" \
    --no-cli-pager
```

#### Restore from Cross-Region Replication

```bash
# Sync from DR bucket to primary bucket
aws s3 sync \
    s3://agentic-deals-production-assets-dr/ \
    s3://agentic-deals-production-assets/ \
    --no-cli-pager
```

### Configuration Recovery

**Recovery Script** (`backend/scripts/ops/restore_configuration.ps1`):
```powershell
param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$Environment = "production"
)

# Download backup from S3 if not local
if (-not (Test-Path $BackupFile)) {
    aws s3 cp $BackupFile . --no-cli-pager
    $BackupFile = Split-Path $BackupFile -Leaf
}

# Extract backup
$extractDir = "config_restore_$(Get-Random)"
Expand-Archive -Path $BackupFile -DestinationPath $extractDir

# Restore SSM Parameters
$ssmFile = "$extractDir/ssm_parameters.json"
$ssmParams = Get-Content $ssmFile | ConvertFrom-Json

foreach ($param in $ssmParams.Parameters) {
    if ($param.Type -eq "SecureString") {
        aws ssm put-parameter --name $param.Name --value $param.Value --type "SecureString" --overwrite --no-cli-pager
    } else {
        aws ssm put-parameter --name $param.Name --value $param.Value --type $param.Type --overwrite --no-cli-pager
    }
    Write-Output "Restored parameter: $($param.Name)"
}

# Clean up
Remove-Item -Recurse -Force $extractDir

Write-Output "Configuration restore completed from: $BackupFile"
```

## Disaster Recovery Plan

### Disaster Definition

A disaster is defined as any event that causes a significant disruption to normal business operations, including but not limited to:

1. Complete failure of the primary AWS region
2. Severe data corruption or loss
3. Catastrophic security breach
4. Infrastructure-wide service outage

### Disaster Recovery Team

| Role | Responsibility | Contact |
|------|----------------|---------|
| DR Coordinator | Overall coordination of recovery efforts | dr-coordinator@agenticdeals.com |
| Database Administrator | Database recovery | dba@agenticdeals.com |
| Infrastructure Engineer | Infrastructure recovery | infra@agenticdeals.com |
| Application Developer | Application validation | dev@agenticdeals.com |
| Security Officer | Security assessment | security@agenticdeals.com |

### Recovery Time and Point Objectives

- **Recovery Time Objective (RTO)**: 2 hours
  - Maximum acceptable time to restore system functionality
- **Recovery Point Objective (RPO)**: 5 minutes
  - Maximum acceptable data loss in terms of time

### Disaster Recovery Procedure

#### 1. Disaster Declaration

The DR Coordinator must officially declare a disaster based on assessment of the situation and notification from monitoring systems or AWS.

#### 2. Team Activation

The DR Coordinator activates the Disaster Recovery Team via PagerDuty and Slack alerts:

```bash
# Send alert to DR team
aws sns publish \
    --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:dr-team-alerts \
    --message "DISASTER DECLARED: [Description of the incident]. DR plan is now active. Join emergency call: [Conference Link]" \
    --no-cli-pager
```

#### 3. Assessment

The team assesses the extent of the disaster and determines the recovery strategy.

#### 4. Infrastructure Recovery

For region-wide failures, activate the standby infrastructure in the secondary region:

```bash
# Execute DR failover CloudFormation stack
aws cloudformation create-stack \
    --stack-name agentic-deals-dr-failover \
    --template-url https://agentic-deals-templates.s3.amazonaws.com/dr-failover.yaml \
    --parameters ParameterKey=Environment,ParameterValue=production \
    --capabilities CAPABILITY_IAM \
    --region us-west-2 \
    --no-cli-pager
```

#### 5. Database Recovery

Promote the read replica in the secondary region to primary:

```bash
# Promote RDS read replica
aws rds promote-read-replica \
    --db-instance-identifier agentic-deals-production-replica \
    --region us-west-2 \
    --no-cli-pager
```

#### 6. Application Deployment

Deploy the application to the new infrastructure:

```bash
# Update ECS service in DR region
aws ecs update-service \
    --cluster agentic-deals-cluster \
    --service agentic-deals-service \
    --force-new-deployment \
    --region us-west-2 \
    --no-cli-pager
```

#### 7. DNS Failover

Update Route 53 health checks and DNS records to point to the new infrastructure:

```bash
# Update Route 53 failover record
aws route53 change-resource-record-sets \
    --hosted-zone-id HOSTED_ZONE_ID \
    --change-batch file://dns-failover.json \
    --no-cli-pager
```

#### 8. Verification

Test the recovered system to ensure functionality:

```bash
# Run verification checks
./backend/scripts/ops/verify_dr_deployment.ps1 -Environment production -Region us-west-2
```

#### 9. Communication

Send notifications to stakeholders about the disaster and recovery status.

#### 10. Post-Disaster Assessment

Once the immediate disaster is mitigated, conduct a thorough root cause analysis and update the DR plan accordingly.

### DR Testing Schedule

| Test Type | Frequency | Last Performed | Next Scheduled |
|-----------|-----------|----------------|----------------|
| Table-top Exercise | Quarterly | 2023-06-15 | 2023-09-15 |
| Infrastructure Recovery | Semi-annually | 2023-04-20 | 2023-10-20 |
| Full DR Simulation | Annually | 2023-02-10 | 2024-02-10 |

## Compliance and Documentation

### Backup and Recovery Logs

All backup and recovery operations are logged for audit purposes. Logs are retained according to the following schedule:

| Log Type | Retention Period | Storage Location |
|----------|------------------|------------------|
| Backup Execution Logs | 1 year | CloudWatch Logs |
| Recovery Operation Logs | 3 years | CloudWatch Logs + S3 Archive |
| Verification Logs | 1 year | CloudWatch Logs |
| Disaster Recovery Logs | 7 years | CloudWatch Logs + S3 Archive |

### Compliance Requirements

This backup and recovery strategy is designed to comply with:

- SOC 2 Type II requirements
- GDPR Article 32 (security of processing)
- CCPA data protection requirements
- Internal SLA commitments

### Documentation Maintenance

This document should be reviewed and updated:

- Quarterly for routine updates
- After any significant infrastructure change
- After any DR plan activation
- After any failed backup or recovery operation

## References

1. [AWS Backup Documentation](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html)
2. [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/current/backup.html)
3. [AWS Disaster Recovery Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html)
4. [System Architecture Documentation](../architecture/architecture.md)
5. [Data Retention Policy](../compliance/data_retention.md) 