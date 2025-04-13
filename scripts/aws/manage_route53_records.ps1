# AWS Route53 DNS Records Management Script
# This script provides utilities for managing Route53 DNS records

param (
    [string]$Action,
    [string]$HostedZoneId,
    [string]$DomainName,
    [string]$RecordType,
    [string]$Value,
    [int]$TTL = 300,
    [switch]$Alias,
    [string]$TargetHostedZoneId,
    [string]$TargetDNS,
    [switch]$OutputOnly,
    [string]$Profile = "agentic-deals-deployment",
    [string]$BatchFile,
    [switch]$Force,
    [switch]$WaitForChange
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Functions
function Write-ColorOutput($ForegroundColor, $Message) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $Message
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success($message) {
    Write-ColorOutput Green "[SUCCESS] $message"
}

function Write-Info($message) {
    Write-ColorOutput Cyan "[INFO] $message"
}

function Write-Warning($message) {
    Write-ColorOutput Yellow "[WARNING] $message"
}

function Write-Error($message) {
    Write-ColorOutput Red "[ERROR] $message"
}

# Check AWS CLI configuration
function Check-AwsConfiguration {
    Write-Info "Checking AWS CLI configuration..."
    try {
        $identity = aws sts get-caller-identity --profile $Profile --no-cli-pager | ConvertFrom-Json
        Write-Success "AWS CLI configured correctly. Using account: $($identity.Account)"
        return $true
    }
    catch {
        Write-Error "AWS CLI not configured correctly. Please run 'aws configure --profile $Profile'"
        return $false
    }
}

# List hosted zones
function List-HostedZones {
    Write-Info "Listing Route53 Hosted Zones..."
    try {
        $zonesOutput = aws route53 list-hosted-zones --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Found $($zonesOutput.HostedZones.Count) hosted zones:"
        
        foreach ($zone in $zonesOutput.HostedZones) {
            $zoneName = $zone.Name -replace '\.$', ''
            $private = if ($zone.Config.PrivateZone) { "(Private)" } else { "(Public)" }
            Write-Host "- Zone ID: $($zone.Id -replace '/hostedzone/', '') | Name: $zoneName $private"
        }
    }
    catch {
        Write-Error "Failed to list hosted zones: $_"
    }
}

# List records in a hosted zone
function List-Records {
    param (
        [Parameter(Mandatory=$true)]
        [string]$ZoneId
    )
    
    Write-Info "Listing records for hosted zone $ZoneId..."
    try {
        $recordsOutput = aws route53 list-resource-record-sets --hosted-zone-id $ZoneId --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Found $($recordsOutput.ResourceRecordSets.Count) records:"
        
        foreach ($record in $recordsOutput.ResourceRecordSets) {
            $name = $record.Name -replace '\.$', ''
            $type = $record.Type
            
            if ($record.AliasTarget) {
                $aliasTargetDNS = $record.AliasTarget.DNSName
                $aliasTargetZone = $record.AliasTarget.HostedZoneId
                $value = "ALIAS to $aliasTargetDNS (Zone: $aliasTargetZone)"
            }
            elseif ($record.ResourceRecords) {
                $recordValues = $record.ResourceRecords.Value -join ', '
                $ttl = $record.TTL
                $value = "$recordValues (TTL: $ttl)"
            }
            else {
                $value = "No value"
            }
            
            Write-Host "- $name | $type | $value"
        }
    }
    catch {
        Write-Error "Failed to list records for zone $ZoneId: $_"
    }
}

# Create a standard DNS record (non-alias)
function Create-StandardRecord {
    param (
        [Parameter(Mandatory=$true)]
        [string]$ZoneId,
        
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$true)]
        [string]$Type,
        
        [Parameter(Mandatory=$true)]
        [string]$Value,
        
        [Parameter(Mandatory=$true)]
        [int]$TTL,
        
        [switch]$JustGenerateJson
    )
    
    # Make sure the name ends with a period for Route53
    if (-not $Name.EndsWith('.')) {
        $Name = "$Name."
    }
    
    # Create the change batch JSON
    $changeBatch = @{
        Changes = @(
            @{
                Action = "UPSERT"
                ResourceRecordSet = @{
                    Name = $Name
                    Type = $Type
                    TTL = $TTL
                    ResourceRecords = @(
                        @{
                            Value = $Value
                        }
                    )
                }
            }
        )
    }
    
    $changeBatchJson = $changeBatch | ConvertTo-Json -Depth 5
    
    if ($JustGenerateJson) {
        return $changeBatchJson
    }
    
    # Create temporary file for the change batch
    $tempFile = [System.IO.Path]::GetTempFileName()
    $changeBatchJson | Out-File -FilePath $tempFile -Encoding utf8
    
    try {
        Write-Info "Creating/updating $Type record for $Name..."
        $changeOutput = aws route53 change-resource-record-sets --hosted-zone-id $ZoneId --change-batch "file://$tempFile" --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Record change initiated successfully."
        Write-Info "Change ID: $($changeOutput.ChangeInfo.Id)"
        Write-Info "Status: $($changeOutput.ChangeInfo.Status)"
        
        # Optionally wait for the change to complete
        if ($WaitForChange) {
            Wait-ForChangeCompletion -ChangeId $changeOutput.ChangeInfo.Id
        }
        
        return $changeOutput.ChangeInfo.Id
    }
    catch {
        Write-Error "Failed to create/update record: $_"
    }
    finally {
        # Clean up
        if (Test-Path $tempFile) {
            Remove-Item $tempFile -Force
        }
    }
}

# Create an alias record
function Create-AliasRecord {
    param (
        [Parameter(Mandatory=$true)]
        [string]$ZoneId,
        
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$true)]
        [string]$Type,
        
        [Parameter(Mandatory=$true)]
        [string]$TargetDNS,
        
        [Parameter(Mandatory=$true)]
        [string]$TargetZoneId,
        
        [switch]$JustGenerateJson
    )
    
    # Make sure the name ends with a period for Route53
    if (-not $Name.EndsWith('.')) {
        $Name = "$Name."
    }
    
    # Make sure the target DNS ends with a period
    if (-not $TargetDNS.EndsWith('.')) {
        $TargetDNS = "$TargetDNS."
    }
    
    # Create the change batch JSON
    $changeBatch = @{
        Changes = @(
            @{
                Action = "UPSERT"
                ResourceRecordSet = @{
                    Name = $Name
                    Type = $Type
                    AliasTarget = @{
                        HostedZoneId = $TargetZoneId
                        DNSName = $TargetDNS
                        EvaluateTargetHealth = $false
                    }
                }
            }
        )
    }
    
    $changeBatchJson = $changeBatch | ConvertTo-Json -Depth 5
    
    if ($JustGenerateJson) {
        return $changeBatchJson
    }
    
    # Create temporary file for the change batch
    $tempFile = [System.IO.Path]::GetTempFileName()
    $changeBatchJson | Out-File -FilePath $tempFile -Encoding utf8
    
    try {
        Write-Info "Creating/updating $Type alias record for $Name pointing to $TargetDNS..."
        $changeOutput = aws route53 change-resource-record-sets --hosted-zone-id $ZoneId --change-batch "file://$tempFile" --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Alias record change initiated successfully."
        Write-Info "Change ID: $($changeOutput.ChangeInfo.Id)"
        Write-Info "Status: $($changeOutput.ChangeInfo.Status)"
        
        # Optionally wait for the change to complete
        if ($WaitForChange) {
            Wait-ForChangeCompletion -ChangeId $changeOutput.ChangeInfo.Id
        }
        
        return $changeOutput.ChangeInfo.Id
    }
    catch {
        Write-Error "Failed to create/update alias record: $_"
    }
    finally {
        # Clean up
        if (Test-Path $tempFile) {
            Remove-Item $tempFile -Force
        }
    }
}

# Delete a DNS record
function Delete-Record {
    param (
        [Parameter(Mandatory=$true)]
        [string]$ZoneId,
        
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$true)]
        [string]$Type,
        
        [switch]$Force
    )
    
    if (-not $Force) {
        $confirmation = Read-Host "Are you sure you want to delete the $Type record for $Name? (y/n)"
        if ($confirmation -ne 'y') {
            Write-Info "Operation cancelled by user."
            return
        }
    }
    
    # Make sure the name ends with a period for Route53
    if (-not $Name.EndsWith('.')) {
        $Name = "$Name."
    }
    
    try {
        # First, get the current record to ensure it exists and get its details
        $recordsOutput = aws route53 list-resource-record-sets --hosted-zone-id $ZoneId --start-record-name $Name --start-record-type $Type --max-items 1 --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        $targetRecord = $null
        foreach ($record in $recordsOutput.ResourceRecordSets) {
            if ($record.Name -eq $Name -and $record.Type -eq $Type) {
                $targetRecord = $record
                break
            }
        }
        
        if (-not $targetRecord) {
            Write-Error "Record $Name of type $Type not found in zone $ZoneId."
            return
        }
        
        # Create a change batch to delete the record
        $changeBatch = @{
            Changes = @(
                @{
                    Action = "DELETE"
                    ResourceRecordSet = $targetRecord
                }
            )
        }
        
        $changeBatchJson = $changeBatch | ConvertTo-Json -Depth 5
        
        # Create temporary file for the change batch
        $tempFile = [System.IO.Path]::GetTempFileName()
        $changeBatchJson | Out-File -FilePath $tempFile -Encoding utf8
        
        Write-Info "Deleting $Type record for $Name..."
        $changeOutput = aws route53 change-resource-record-sets --hosted-zone-id $ZoneId --change-batch "file://$tempFile" --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Record deletion initiated successfully."
        Write-Info "Change ID: $($changeOutput.ChangeInfo.Id)"
        Write-Info "Status: $($changeOutput.ChangeInfo.Status)"
        
        # Optionally wait for the change to complete
        if ($WaitForChange) {
            Wait-ForChangeCompletion -ChangeId $changeOutput.ChangeInfo.Id
        }
        
        return $changeOutput.ChangeInfo.Id
    }
    catch {
        Write-Error "Failed to delete record: $_"
    }
    finally {
        # Clean up
        if (Test-Path $tempFile) {
            Remove-Item $tempFile -Force
        }
    }
}

# Process changes from a batch file
function Process-BatchFile {
    param (
        [Parameter(Mandatory=$true)]
        [string]$FilePath
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Error "Batch file $FilePath not found."
        return
    }
    
    try {
        $batchData = Get-Content -Path $FilePath -Raw | ConvertFrom-Json
        
        if (-not $batchData.Changes) {
            Write-Error "Invalid batch file format. Missing 'Changes' array."
            return
        }
        
        # Create temporary file for the change batch
        $tempFile = [System.IO.Path]::GetTempFileName()
        $batchData | ConvertTo-Json -Depth 5 | Out-File -FilePath $tempFile -Encoding utf8
        
        Write-Info "Processing batch file with $($batchData.Changes.Count) changes..."
        $changeOutput = aws route53 change-resource-record-sets --hosted-zone-id $HostedZoneId --change-batch "file://$tempFile" --profile $Profile --no-cli-pager | ConvertFrom-Json
        
        Write-Success "Batch changes initiated successfully."
        Write-Info "Change ID: $($changeOutput.ChangeInfo.Id)"
        Write-Info "Status: $($changeOutput.ChangeInfo.Status)"
        
        # Optionally wait for the change to complete
        if ($WaitForChange) {
            Wait-ForChangeCompletion -ChangeId $changeOutput.ChangeInfo.Id
        }
        
        return $changeOutput.ChangeInfo.Id
    }
    catch {
        Write-Error "Failed to process batch file: $_"
    }
    finally {
        # Clean up
        if (Test-Path $tempFile) {
            Remove-Item $tempFile -Force
        }
    }
}

# Wait for a change to complete
function Wait-ForChangeCompletion {
    param (
        [Parameter(Mandatory=$true)]
        [string]$ChangeId
    )
    
    Write-Info "Waiting for change to complete..."
    
    $status = ""
    $counter = 0
    $maxAttempts = 30
    $delaySeconds = 10
    
    while ($status -ne "INSYNC" -and $counter -lt $maxAttempts) {
        $counter++
        
        try {
            $changeInfo = aws route53 get-change --id $ChangeId --profile $Profile --no-cli-pager | ConvertFrom-Json
            $status = $changeInfo.ChangeInfo.Status
            
            Write-Info "Current status: $status (Attempt $counter of $maxAttempts)"
            
            if ($status -eq "INSYNC") {
                Write-Success "Change completed successfully."
                return $true
            }
            
            Start-Sleep -Seconds $delaySeconds
        }
        catch {
            Write-Error "Error checking change status: $_"
            return $false
        }
    }
    
    if ($status -ne "INSYNC") {
        Write-Warning "Timed out waiting for change to complete. Last status: $status"
        return $false
    }
    
    return $true
}

# Main execution
if (-not (Check-AwsConfiguration)) {
    exit 1
}

# Process based on action
switch ($Action) {
    "list-zones" {
        List-HostedZones
    }
    
    "list-records" {
        if (-not $HostedZoneId) {
            Write-Error "HostedZoneId parameter is required for list-records action."
            exit 1
        }
        
        List-Records -ZoneId $HostedZoneId
    }
    
    "create" {
        if (-not $HostedZoneId) {
            Write-Error "HostedZoneId parameter is required for create action."
            exit 1
        }
        
        if (-not $DomainName) {
            Write-Error "DomainName parameter is required for create action."
            exit 1
        }
        
        if (-not $RecordType) {
            Write-Error "RecordType parameter is required for create action."
            exit 1
        }
        
        if ($Alias) {
            if (-not $TargetHostedZoneId) {
                Write-Error "TargetHostedZoneId parameter is required for alias records."
                exit 1
            }
            
            if (-not $TargetDNS) {
                Write-Error "TargetDNS parameter is required for alias records."
                exit 1
            }
            
            if ($OutputOnly) {
                $json = Create-AliasRecord -ZoneId $HostedZoneId -Name $DomainName -Type $RecordType -TargetDNS $TargetDNS -TargetZoneId $TargetHostedZoneId -JustGenerateJson
                Write-Output $json
            } else {
                Create-AliasRecord -ZoneId $HostedZoneId -Name $DomainName -Type $RecordType -TargetDNS $TargetDNS -TargetZoneId $TargetHostedZoneId
            }
        } else {
            if (-not $Value) {
                Write-Error "Value parameter is required for standard records."
                exit 1
            }
            
            if ($OutputOnly) {
                $json = Create-StandardRecord -ZoneId $HostedZoneId -Name $DomainName -Type $RecordType -Value $Value -TTL $TTL -JustGenerateJson
                Write-Output $json
            } else {
                Create-StandardRecord -ZoneId $HostedZoneId -Name $DomainName -Type $RecordType -Value $Value -TTL $TTL
            }
        }
    }
    
    "delete" {
        if (-not $HostedZoneId) {
            Write-Error "HostedZoneId parameter is required for delete action."
            exit 1
        }
        
        if (-not $DomainName) {
            Write-Error "DomainName parameter is required for delete action."
            exit 1
        }
        
        if (-not $RecordType) {
            Write-Error "RecordType parameter is required for delete action."
            exit 1
        }
        
        Delete-Record -ZoneId $HostedZoneId -Name $DomainName -Type $RecordType -Force:$Force
    }
    
    "process-batch" {
        if (-not $HostedZoneId) {
            Write-Error "HostedZoneId parameter is required for process-batch action."
            exit 1
        }
        
        if (-not $BatchFile) {
            Write-Error "BatchFile parameter is required for process-batch action."
            exit 1
        }
        
        Process-BatchFile -FilePath $BatchFile
    }
    
    default {
        Write-Error "Invalid or missing Action parameter. Valid actions are: list-zones, list-records, create, delete, process-batch"
        Write-Info "Examples:"
        Write-Info "  ./manage_route53_records.ps1 -Action list-zones"
        Write-Info "  ./manage_route53_records.ps1 -Action list-records -HostedZoneId Z07320182C90HB43O7XCA"
        Write-Info "  ./manage_route53_records.ps1 -Action create -HostedZoneId Z07320182C90HB43O7XCA -DomainName example.com -RecordType A -Value 192.0.2.1 -TTL 300"
        Write-Info "  ./manage_route53_records.ps1 -Action create -HostedZoneId Z07320182C90HB43O7XCA -DomainName example.com -RecordType A -Alias -TargetHostedZoneId Z2FDTNDATAQYW2 -TargetDNS d111111abcdef8.cloudfront.net"
        Write-Info "  ./manage_route53_records.ps1 -Action delete -HostedZoneId Z07320182C90HB43O7XCA -DomainName example.com -RecordType A -Force"
        Write-Info "  ./manage_route53_records.ps1 -Action process-batch -HostedZoneId Z07320182C90HB43O7XCA -BatchFile batch.json"
        exit 1
    }
} 