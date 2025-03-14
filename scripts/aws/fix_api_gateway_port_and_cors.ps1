# Fix API Gateway Integration Port and CORS Issues
# This script fixes API Gateway integration issues with incorrect port and updates CORS settings

param(
    [Parameter(Mandatory=$false)]
    [string]$ProfileName = "agentic-deals-deployment",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$false)]
    [string]$ApiId = "7oxq7ujcmc",
    
    [Parameter(Mandatory=$false)]
    [string]$StageName = "prod",
    
    [Parameter(Mandatory=$false)]
    [string[]]$AllowedOrigins = @("https://d3irpl0o2ddv9y.cloudfront.net", "https://rebaton.ai", "*"),
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

# Set error action preference
$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

function Write-Header {
    param ([string]$Message)
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

# Validate AWS CLI profile
try {
    $result = aws configure list --profile $ProfileName 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: AWS CLI profile '$ProfileName' not found or not configured correctly." -ForegroundColor Red
        Write-Host "Please run 'aws configure --profile $ProfileName' to set up the profile." -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "ERROR: AWS CLI profile '$ProfileName' not found or not configured correctly." -ForegroundColor Red
    Write-Host "Please run 'aws configure --profile $ProfileName' to set up the profile." -ForegroundColor Red
    exit 1
}

# Print configuration
Write-Header "Fix Configuration"
Write-Host "AWS Profile: $ProfileName"
Write-Host "AWS Region: $Region"
Write-Host "API Gateway ID: $ApiId"
Write-Host "Stage Name: $StageName"
Write-Host "Allowed Origins: $($AllowedOrigins -join ', ')"
Write-Host "Dry Run: $DryRun"

# Step 1: Get all resources for the API
Write-Header "Getting API Resources"
try {
    $resourcesOutput = aws apigateway get-resources --profile $ProfileName --region $Region --rest-api-id $ApiId --no-cli-pager
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to get API resources." -ForegroundColor Red
        exit 1
    }
    $resources = $resourcesOutput | ConvertFrom-Json
    Write-Host "Found $($resources.items.Count) resources in API Gateway" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: Failed to get API resources." -ForegroundColor Red
    exit 1
}

# Step 2: Check and fix integration URIs for each resource
Write-Header "Checking and Fixing Integration URIs"
$fixedCount = 0
$alreadyCorrectCount = 0
$nonIntegrationCount = 0

foreach ($resource in $resources.items) {
    $resourceId = $resource.id
    $resourcePath = $resource.path
    
    # Get all methods for this resource
    try {
        $methodsOutput = aws apigateway get-resource --profile $ProfileName --region $Region --rest-api-id $ApiId --resource-id $resourceId --no-cli-pager --embed methods
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  WARNING: Failed to get methods for resource $resourceId" -ForegroundColor Yellow
            continue
        }
        
        $resourceWithMethods = $methodsOutput | ConvertFrom-Json
        $resourceMethods = $resourceWithMethods.resourceMethods
        
        if ($null -eq $resourceMethods) {
            Write-Host "  No methods found for resource $resourceId" -ForegroundColor Yellow
            continue
        }
        
        foreach ($methodName in $resourceMethods.PSObject.Properties.Name) {
            try {
                $integrationOutput = aws apigateway get-integration --profile $ProfileName --region $Region --rest-api-id $ApiId --resource-id $resourceId --http-method $methodName --no-cli-pager
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "  WARNING: Failed to get integration for $methodName" -ForegroundColor Yellow
                    $nonIntegrationCount++
                    continue
                }
                
                $integration = $integrationOutput | ConvertFrom-Json
                $integrationUri = $integration.uri
                
                if ([string]::IsNullOrEmpty($integrationUri)) {
                    Write-Host "  WARNING: Integration URI is null or empty for $methodName" -ForegroundColor Yellow
                    $nonIntegrationCount++
                    continue
                }
                
                # Check for port 80 in the URI
                if ($integrationUri.Contains(":80/")) {
                    # Replace port 80 with 8000
                    $fixedUri = $integrationUri.Replace(":80/", ":8000/")
                    
                    Write-Host "  Found incorrect port for $methodName" -ForegroundColor Yellow
                    
                    # Fix the integration URI
                    if (-not $DryRun) {
                        $updateCmd = "aws apigateway update-integration --profile $ProfileName --region $Region --rest-api-id $ApiId --resource-id $resourceId --http-method $methodName --patch-operations op=replace,path=/uri,value='$fixedUri' --no-cli-pager"
                        Invoke-Expression $updateCmd
                        
                        if ($LASTEXITCODE -ne 0) {
                            Write-Host "  ERROR: Failed to update integration URI for $methodName" -ForegroundColor Red
                        }
                        else {
                            Write-Host "  Successfully updated integration URI for $methodName" -ForegroundColor Green
                            $fixedCount++
                        }
                    }
                    else {
                        Write-Host "  DRY RUN: Would update integration URI for $methodName" -ForegroundColor Yellow
                        $fixedCount++
                    }
                }
                elseif ($integrationUri.Contains(":8000/")) {
                    Write-Host "  Integration URI for $methodName is already using correct port (8000)" -ForegroundColor Green
                    $alreadyCorrectCount++
                }
                else {
                    Write-Host "  Integration URI for $methodName is using a different format or no port" -ForegroundColor Yellow
                    $nonIntegrationCount++
                }
            }
            catch {
                Write-Host "  WARNING: Error processing integration for $methodName" -ForegroundColor Yellow
                $nonIntegrationCount++
                continue
            }
        }
    }
    catch {
        Write-Host "  WARNING: Error processing resource $resourceId" -ForegroundColor Yellow
        continue
    }
}

Write-Host "Integration URIs fixed: $fixedCount" -ForegroundColor Green
Write-Host "Integration URIs already correct: $alreadyCorrectCount" -ForegroundColor Green
Write-Host "Resources without standard integration URIs: $nonIntegrationCount" -ForegroundColor Yellow

# Step 3: Update CORS configuration for the API
Write-Header "Updating CORS Configuration"

# Update CORS settings for all necessary resources
foreach ($resource in $resources.items) {
    $resourceId = $resource.id
    $resourcePath = $resource.path
    
    # Skip the root resource as it typically doesn't need CORS
    if ($resourcePath -eq "/") {
        continue
    }
    
    # Check if the resource has an OPTIONS method
    try {
        $methodsOutput = aws apigateway get-resource --profile $ProfileName --region $Region --rest-api-id $ApiId --resource-id $resourceId --no-cli-pager --embed methods
        $resourceWithMethods = $methodsOutput | ConvertFrom-Json
        $hasOptions = $resourceWithMethods.resourceMethods -and $resourceWithMethods.resourceMethods.PSObject.Properties.Name -contains "OPTIONS"
        
        if ($hasOptions) {
            Write-Host "Updating CORS settings for resource $resourcePath" -ForegroundColor Yellow
            
            if (-not $DryRun) {
                $corsCmd = "aws apigateway update-method-response --profile $ProfileName --region $Region --rest-api-id $ApiId --resource-id $resourceId --http-method OPTIONS --status-code 200 --patch-operations op=replace,path=/responseParameters/method.response.header.Access-Control-Allow-Headers,value='`"Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token`"' op=replace,path=/responseParameters/method.response.header.Access-Control-Allow-Methods,value='`"GET,POST,PUT,DELETE,OPTIONS,PATCH`"' op=replace,path=/responseParameters/method.response.header.Access-Control-Allow-Origin,value='`"*`"' --no-cli-pager"
                Invoke-Expression $corsCmd
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "  ERROR: Failed to update CORS settings for resource $resourcePath" -ForegroundColor Red
                }
                else {
                    Write-Host "  Successfully updated CORS settings for resource $resourcePath" -ForegroundColor Green
                }
            }
            else {
                Write-Host "  DRY RUN: Would update CORS settings for resource $resourcePath" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "  Resource $resourcePath does not have OPTIONS method, skipping CORS configuration" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  WARNING: Error checking OPTIONS method for resource $resourceId" -ForegroundColor Yellow
        continue
    }
}

# Step 4: Create a deployment to apply changes
Write-Header "Deploying Changes"

if (-not $DryRun) {
    try {
        $deployCmd = "aws apigateway create-deployment --profile $ProfileName --region $Region --rest-api-id $ApiId --stage-name $StageName --description 'Fixed integration URI port issues and updated CORS settings' --no-cli-pager"
        Invoke-Expression $deployCmd
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to create deployment." -ForegroundColor Red
            exit 1
        }
        
        Write-Host "Successfully created deployment to apply changes." -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: Failed to create deployment." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "DRY RUN: Would create deployment to apply changes." -ForegroundColor Yellow
}

# Step 5: Also ensure correct health check endpoint is used in container configuration
Write-Header "Health Check Endpoint Fix"
Write-Host "NOTE: Health check endpoint in the task definition should point to /health instead of /api/v1/health" -ForegroundColor Yellow
Write-Host "Current container health check in hardcoded-task-definition.json: curl -f http://localhost:8000/health || exit 1" -ForegroundColor Green
Write-Host "Make sure any load balancer health checks also use the /health endpoint" -ForegroundColor Yellow

Write-Header "Completed Successfully"
Write-Host "Integration URIs fixed: $fixedCount" -ForegroundColor Green
Write-Host "Please run a test request to verify the fixes." -ForegroundColor Yellow 