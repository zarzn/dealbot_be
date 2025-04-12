#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sets up AWS SES email verification for the AI Agentic Deals System.
    
.DESCRIPTION
    This script helps configure AWS SES for sending emails in the AI Agentic Deals System.
    It verifies email addresses, optionally verifies domains, and outputs configuration settings.
    
.PARAMETER EmailAddress
    The email address to verify for sending emails.
    
.PARAMETER Domain
    Optional. The domain to verify for sending emails. If provided, the script will verify the domain instead of individual emails.
    
.PARAMETER Region
    AWS region to use for SES. Defaults to us-east-1.
    
.PARAMETER Profile
    AWS profile to use. Defaults to agentic-deals-deployment.
    
.PARAMETER CreateConfigSet
    If specified, creates a configuration set for email tracking.
    
.EXAMPLE
    ./setup_ses_email.ps1 -EmailAddress "noreply@yourdomain.com"
    
.EXAMPLE
    ./setup_ses_email.ps1 -Domain "yourdomain.com" -Region "us-west-2" -CreateConfigSet
#>

param (
    [Parameter(Mandatory=$false)]
    [string]$EmailAddress = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Domain = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$false)]
    [string]$Profile = "agentic-deals-deployment",
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateConfigSet = $false
)

# Check if either EmailAddress or Domain is provided
if ([string]::IsNullOrEmpty($EmailAddress) -and [string]::IsNullOrEmpty($Domain)) {
    Write-Host "Error: You must provide either an EmailAddress or a Domain to verify." -ForegroundColor Red
    exit 1
}

# Check if AWS CLI is installed
try {
    $awsVersion = aws --version
    Write-Host "AWS CLI is installed: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: AWS CLI is not installed or not in PATH. Please install AWS CLI first." -ForegroundColor Red
    exit 1
}

# Check if AWS profile exists
try {
    $profileCheck = aws configure list --profile $Profile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: AWS profile '$Profile' does not exist. Please create it first with 'aws configure --profile $Profile'." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using AWS profile: $Profile" -ForegroundColor Green
} catch {
    Write-Host "Error checking AWS profile: $_" -ForegroundColor Red
    exit 1
}

# Set AWS region
$env:AWS_REGION = $Region
Write-Host "Using AWS region: $Region" -ForegroundColor Green

# Function to check SES sending status
function Check-SESSendingStatus {
    try {
        $sendingStatusJson = aws ses get-account-sending-enabled --region $Region --profile $Profile --no-cli-pager
        $sendingStatus = $sendingStatusJson | ConvertFrom-Json
        
        if ($sendingStatus.Enabled) {
            Write-Host "SES account sending is ENABLED" -ForegroundColor Green
        } else {
            Write-Host "SES account sending is DISABLED. You may need to request production access." -ForegroundColor Yellow
        }
        
        $quotaJson = aws ses get-send-quota --region $Region --profile $Profile --no-cli-pager
        $quota = $quotaJson | ConvertFrom-Json
        
        Write-Host "SES Sending Quota:" -ForegroundColor Cyan
        Write-Host "  Max 24 Hour Send: $($quota.Max24HourSend)" -ForegroundColor Cyan
        Write-Host "  Max Send Rate: $($quota.MaxSendRate) emails/second" -ForegroundColor Cyan
        Write-Host "  Sent Last 24 Hours: $($quota.SentLast24Hours)" -ForegroundColor Cyan
        
    } catch {
        Write-Host "Error checking SES sending status: $_" -ForegroundColor Red
    }
}

# Create SES Configuration Set if requested
if ($CreateConfigSet) {
    $configSetName = "agentic-deals-ses-config"
    
    try {
        # Check if configuration set already exists
        $configSets = aws ses list-configuration-sets --region $Region --profile $Profile --no-cli-pager | ConvertFrom-Json
        $configSetExists = $false
        
        if ($configSets.ConfigurationSets) {
            foreach ($set in $configSets.ConfigurationSets) {
                if ($set.Name -eq $configSetName) {
                    $configSetExists = $true
                    break
                }
            }
        }
        
        if ($configSetExists) {
            Write-Host "Configuration set '$configSetName' already exists." -ForegroundColor Yellow
        } else {
            # Create configuration set
            $result = aws ses create-configuration-set --configuration-set "Name=$configSetName" --region $Region --profile $Profile --no-cli-pager
            Write-Host "Created SES configuration set: $configSetName" -ForegroundColor Green
            
            # You can add event destinations here if needed
            # aws ses create-configuration-set-event-destination ...
        }
    } catch {
        Write-Host "Error creating SES configuration set: $_" -ForegroundColor Red
    }
}

# Verify email address if provided
if (-not [string]::IsNullOrEmpty($EmailAddress)) {
    try {
        # Check if the email address is already verified
        $verifiedEmails = aws ses list-verified-email-addresses --region $Region --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        if ($verifiedEmails.VerifiedEmailAddresses -contains $EmailAddress) {
            Write-Host "Email address '$EmailAddress' is already verified." -ForegroundColor Yellow
        } else {
            # Verify the email address
            aws ses verify-email-identity --email-address $EmailAddress --region $Region --profile $Profile --no-cli-pager
            
            Write-Host "Verification email sent to '$EmailAddress'. Please check your inbox and click the verification link." -ForegroundColor Green
            Write-Host "Note: You cannot send emails from this address until verification is complete." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Error verifying email address: $_" -ForegroundColor Red
    }
}

# Verify domain if provided
if (-not [string]::IsNullOrEmpty($Domain)) {
    try {
        # Check if the domain is already verified
        $verifiedDomains = aws ses list-verified-domain-identities --region $Region --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        if ($verifiedDomains.VerifiedDomainIdentities.PSObject.Properties.Name -contains $Domain) {
            Write-Host "Domain '$Domain' is already verified." -ForegroundColor Yellow
        } else {
            # Verify the domain
            aws ses verify-domain-identity --domain $Domain --region $Region --profile $Profile --no-cli-pager
            
            # Get the verification token
            $identityVerification = aws ses get-identity-verification-attributes --identities $Domain --region $Region --profile $Profile --no-cli-pager | ConvertFrom-Json
            $verificationToken = $identityVerification.VerificationAttributes.$Domain.VerificationToken
            
            Write-Host "Domain verification initiated for '$Domain'." -ForegroundColor Green
            Write-Host "Please add the following TXT record to your DNS configuration:" -ForegroundColor Yellow
            Write-Host "_amazonses.$Domain  TXT  $verificationToken" -ForegroundColor Cyan
            
            # Optionally set up DKIM
            aws ses verify-domain-dkim --domain $Domain --region $Region --profile $Profile --no-cli-pager
            
            $dkimTokens = aws ses get-identity-dkim-attributes --identities $Domain --region $Region --profile $Profile --no-cli-pager | ConvertFrom-Json
            
            Write-Host "DKIM verification initiated for '$Domain'." -ForegroundColor Green
            Write-Host "Please add the following CNAME records to your DNS configuration:" -ForegroundColor Yellow
            
            $dkimTokens = ($dkimTokens.DkimAttributes.$Domain.DkimTokens)
            foreach ($token in $dkimTokens) {
                Write-Host "$token._domainkey.$Domain  CNAME  $token.dkim.amazonses.com" -ForegroundColor Cyan
            }
            
            Write-Host "Note: DNS changes may take 24-48 hours to propagate." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Error verifying domain: $_" -ForegroundColor Red
    }
}

# Check SES sending status and quota
Check-SESSendingStatus

# Get Identity ARN if available (useful for source ARN in configuration)
if (-not [string]::IsNullOrEmpty($EmailAddress)) {
    $accountId = aws sts get-caller-identity --profile $Profile --query 'Account' --output text
    $identityArn = 'arn:aws:ses:' + $Region + ':' + $accountId + ':identity/' + $EmailAddress
    Write-Host "`nEmail Identity ARN: $identityArn" -ForegroundColor Green
}

if (-not [string]::IsNullOrEmpty($Domain)) {
    $accountId = aws sts get-caller-identity --profile $Profile --query 'Account' --output text
    $identityArn = 'arn:aws:ses:' + $Region + ':' + $accountId + ':identity/' + $Domain
    Write-Host "`nDomain Identity ARN: $identityArn" -ForegroundColor Green
}

# Print configuration guidance
Write-Host "`nAdd the following to your .env file:" -ForegroundColor Cyan
Write-Host "EMAIL_BACKEND=ses" -ForegroundColor White
Write-Host "EMAIL_FROM=`"Your Name <$EmailAddress>`"" -ForegroundColor White
Write-Host "AWS_SES_REGION=$Region" -ForegroundColor White
Write-Host "# AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY should be set securely" -ForegroundColor White

if ($CreateConfigSet) {
    Write-Host "AWS_SES_CONFIGURATION_SET=$configSetName" -ForegroundColor White
}

if (-not [string]::IsNullOrEmpty($identityArn)) {
    Write-Host "AWS_SES_SOURCE_ARN=$identityArn" -ForegroundColor White
}

Write-Host "`nTo test the email functionality, run:" -ForegroundColor Green
Write-Host "python -m scripts.test_ses_email your-recipient@example.com" -ForegroundColor White 