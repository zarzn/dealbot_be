# Master script for testing AWS integrations and configuring logging
# This script provides a simple interface to run all the API Gateway testing and logging scripts

param(
    [Parameter(Mandatory=$false)]
    [string]$Action = "menu",
    
    [Parameter(Mandatory=$false)]
    [string]$RestApiUrl = $env:API_GATEWAY_URL,
    
    [Parameter(Mandatory=$false)]
    [string]$WebSocketUrl = $env:WEBSOCKET_API_GATEWAY_URL,
    
    [Parameter(Mandatory=$false)]
    [string]$FrontendUrl = $env:NEXT_PUBLIC_APP_URL,
    
    [Parameter(Mandatory=$false)]
    [string]$RestApiId = $env:API_GATEWAY_ID,
    
    [Parameter(Mandatory=$false)]
    [string]$WebSocketApiId = $env:WEBSOCKET_API_GATEWAY_ID,
    
    [Parameter(Mandatory=$false)]
    [string]$Stage = $env:API_GATEWAY_STAGE,
    
    [Parameter(Mandatory=$false)]
    [string]$Username,
    
    [Parameter(Mandatory=$false)]
    [string]$Password,
    
    [Parameter(Mandatory=$false)]
    [string]$Region = $env:AWS_REGION,
    
    [Parameter(Mandatory=$false)]
    [switch]$Auto
)

# Script locations
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$testApiScript = Join-Path $scriptDir "test_api_gateway.ps1"
$testWebSocketScript = Join-Path $scriptDir "test_websocket_api.ps1"
$testE2eScript = Join-Path $scriptDir "test_e2e.ps1"
$awsScriptsDir = Join-Path $scriptDir "aws"
$configureLoggingScript = Join-Path $awsScriptsDir "configure_api_gateway_logging.py"
$monitorLogsScript = Join-Path $awsScriptsDir "monitor_api_gateway_logs.py"

# Initialize AWS Scripts directory if it doesn't exist
if (-not (Test-Path $awsScriptsDir)) {
    New-Item -ItemType Directory -Path $awsScriptsDir | Out-Null
}

# Check Python installation
$pythonInstalled = $null
try {
    $pythonVersion = python --version
    $pythonInstalled = $true
} catch {
    $pythonInstalled = $false
}

# Load environment variables from .env files
function Load-EnvFile {
    param (
        [string]$envFile
    )
    
    if (Test-Path $envFile) {
        Write-Host "Loading environment from: $envFile" -ForegroundColor Gray
        Get-Content $envFile | ForEach-Object {
            if ((-not [string]::IsNullOrWhiteSpace($_)) -and (-not $_.StartsWith("#"))) {
                $key, $value = $_ -split '=', 2
                if ($key -and $value) {
                    $key = $key.Trim()
                    $value = $value.Trim()
                    # Remove quotes if present
                    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                        $value = $value.Substring(1, $value.Length - 2)
                    }
                    [Environment]::SetEnvironmentVariable($key, $value, "Process")
                }
            }
        }
        return $true
    }
    return $false
}

# Auto-discover API Gateway IDs
function Discover-ApiGatewayIds {
    # Try to get API Gateway IDs from URLs if provided
    if (-not $RestApiId -and $RestApiUrl) {
        if ($RestApiUrl -match "https{0,1}://([a-z0-9]+)\.execute-api\.") {
            $script:RestApiId = $matches[1]
            Write-Host "Extracted REST API ID from URL: $RestApiId" -ForegroundColor Cyan
        }
    }
    
    if (-not $WebSocketApiId -and $WebSocketUrl) {
        if ($WebSocketUrl -match "wss{0,1}://([a-z0-9]+)\.execute-api\.") {
            $script:WebSocketApiId = $matches[1]
            Write-Host "Extracted WebSocket API ID from URL: $WebSocketApiId" -ForegroundColor Cyan
        }
    }
    
    # Try loading from .env files
    if (-not $RestApiId -or -not $WebSocketApiId -or -not $Stage) {
        $backendDir = Split-Path -Parent $scriptDir
        $envFiles = @(
            (Join-Path $backendDir ".env"),
            (Join-Path $backendDir ".env.production"),
            (Join-Path $backendDir ".env.development"),
            (Join-Path (Split-Path -Parent $backendDir) ".env")
        )
        
        foreach ($envFile in $envFiles) {
            if (Load-EnvFile $envFile) {
                # Check if we found values after loading
                if (-not $RestApiId) { $script:RestApiId = $env:API_GATEWAY_ID }
                if (-not $WebSocketApiId) { $script:WebSocketApiId = $env:WEBSOCKET_API_GATEWAY_ID }
                if (-not $Stage) { $script:Stage = $env:API_GATEWAY_STAGE }
                if (-not $Region) { $script:Region = $env:AWS_REGION }
                
                # Extract from URLs if available
                if (-not $RestApiId -and $env:API_GATEWAY_URL) {
                    if ($env:API_GATEWAY_URL -match "https{0,1}://([a-z0-9]+)\.execute-api\.") {
                        $script:RestApiId = $matches[1]
                        Write-Host "Extracted REST API ID from environment URL: $RestApiId" -ForegroundColor Cyan
                    }
                }
                
                if (-not $WebSocketApiId -and $env:WEBSOCKET_API_GATEWAY_URL) {
                    if ($env:WEBSOCKET_API_GATEWAY_URL -match "wss{0,1}://([a-z0-9]+)\.execute-api\.") {
                        $script:WebSocketApiId = $matches[1]
                        Write-Host "Extracted WebSocket API ID from environment URL: $WebSocketApiId" -ForegroundColor Cyan
                    }
                }
            }
        }
    }
    
    # If Stage is still not set, use default
    if (-not $Stage) {
        $script:Stage = "prod"
        Write-Host "Using default stage: prod" -ForegroundColor Cyan
    }
    
    # Try to discover using AWS CLI if still not found
    if ((-not $RestApiId -or -not $WebSocketApiId) -and $Auto) {
        try {
            # Check if AWS CLI is available
            try { $awsVersion = aws --version } catch { Write-Host "AWS CLI not available for auto-discovery" -ForegroundColor Yellow; return }
            
            Write-Host "Attempting to discover API Gateway IDs from AWS CLI..." -ForegroundColor Cyan
            
            if (-not $RestApiId) {
                Write-Host "  Looking for REST API Gateway..." -ForegroundColor Gray
                $restApis = aws apigateway get-rest-apis --output json | ConvertFrom-Json
                if ($restApis -and $restApis.items -and $restApis.items.Count -gt 0) {
                    # Sort by created date (descending) and take the first
                    $latestApi = $restApis.items | Sort-Object -Property createdDate -Descending | Select-Object -First 1
                    $script:RestApiId = $latestApi.id
                    Write-Host "  Found REST API ID: $RestApiId (Name: $($latestApi.name))" -ForegroundColor Green
                }
            }
            
            if (-not $WebSocketApiId) {
                Write-Host "  Looking for WebSocket API Gateway..." -ForegroundColor Gray
                # Use AWS CLI with appropriate filter to get only WebSocket APIs
                $wsApis = aws apigatewayv2 get-apis --output json | ConvertFrom-Json
                if ($wsApis -and $wsApis.Items) {
                    $webSocketApis = $wsApis.Items | Where-Object { $_.ProtocolType -eq "WEBSOCKET" }
                    if ($webSocketApis -and $webSocketApis.Count -gt 0) {
                        # Sort by created date (descending) and take the first
                        $latestWsApi = $webSocketApis | Sort-Object -Property CreatedDate -Descending | Select-Object -First 1
                        $script:WebSocketApiId = $latestWsApi.ApiId
                        Write-Host "  Found WebSocket API ID: $WebSocketApiId (Name: $($latestWsApi.Name))" -ForegroundColor Green
                    }
                }
            }
        }
        catch {
            Write-Host "Error during AWS CLI discovery: $_" -ForegroundColor Red
        }
    }
    
    # Return true if we have at least the REST API ID
    return $null -ne $RestApiId
}

# Function to display menu
function Show-Menu {
    Clear-Host
    Write-Host "=== AI Agentic Deals System - AWS Integration Testing ==="
    Write-Host "1: Test REST API Gateway"
    Write-Host "2: Test WebSocket API Gateway"
    Write-Host "3: Run End-to-End Tests"
    Write-Host "4: Configure API Gateway Logging"
    Write-Host "5: Monitor API Gateway Logs"
    Write-Host "6: Install Required AWS Dependencies"
    Write-Host "7: Auto-Configure CloudWatch Logging (No Prompts)"
    Write-Host "Q: Quit"
    Write-Host "=================================================="
}

# Function to install dependencies
function Install-AwsDependencies {
    # Check if we have Python
    if (-not $pythonInstalled) {
        Write-Host "Python is not installed or not in PATH. Please install Python 3.7+" -ForegroundColor Red
        return
    }
    
    $requirementsFile = Join-Path (Split-Path -Parent $scriptDir) "requirements-aws.txt"
    
    # Check if requirements file exists
    if (-not (Test-Path $requirementsFile)) {
        Write-Error "AWS requirements file not found: $requirementsFile"
        return
    }
    
    Write-Host "Installing AWS dependencies from $requirementsFile..." -ForegroundColor Cyan
    & python -m pip install -r $requirementsFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "AWS dependencies installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to install AWS dependencies. See error details above." -ForegroundColor Red
    }
}

# Function to run auto-configure CloudWatch logging
function Auto-ConfigureLogging {
    # Check Python installation
    if (-not $pythonInstalled) {
        Write-Host "Python is not installed or not in PATH. Please install Python 3.7+" -ForegroundColor Red
        return
    }
    
    # Check if script exists
    if (-not (Test-Path $configureLoggingScript)) {
        Write-Error "Configuration script not found: $configureLoggingScript"
        return
    }
    
    # Discover API Gateway IDs
    Write-Host "Attempting to discover AWS resources..." -ForegroundColor Cyan
    
    $discovered = Discover-ApiGatewayIds
    
    # Validate we have sufficient information
    $missingInfo = @()
    if (-not $RestApiId) { $missingInfo += "REST API Gateway ID" }
    # WebSocket is optional so don't add to missing info
    
    if ($missingInfo.Count -gt 0) {
        Write-Host "Unable to automatically discover required AWS resources:" -ForegroundColor Red
        Write-Host "  Missing: $($missingInfo -join ', ')" -ForegroundColor Red
        Write-Host "Please set environment variables or use parameter values:" -ForegroundColor Yellow
        Write-Host "  -RestApiId    API Gateway ID (or API_GATEWAY_ID environment variable)" -ForegroundColor Yellow
        Write-Host "  -RestApiUrl   API Gateway URL (or API_GATEWAY_URL environment variable)" -ForegroundColor Yellow
        Write-Host "  -Stage        API Stage name (or API_GATEWAY_STAGE environment variable)" -ForegroundColor Yellow
        return
    }
    
    # Build parameters for the script
    $params = @()
    
    if ($RestApiId) {
        $params += @("--rest-api-id", $RestApiId)
        Write-Host "Using REST API Gateway ID: $RestApiId" -ForegroundColor Cyan
    }
    
    if ($WebSocketApiId) {
        $params += @("--ws-api-id", $WebSocketApiId)
        Write-Host "Using WebSocket API Gateway ID: $WebSocketApiId" -ForegroundColor Cyan
    }
    
    $params += @("--stage", $Stage)
    Write-Host "Using Stage: $Stage" -ForegroundColor Cyan
    
    if ($Region) {
        $params += @("--region", $Region)
        Write-Host "Using Region: $Region" -ForegroundColor Cyan
    }
    
    # Run the script with parameters
    Write-Host "Configuring CloudWatch logging..." -ForegroundColor Green
    & python $configureLoggingScript @params
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "CloudWatch logging configuration completed successfully!" -ForegroundColor Green
        
        # Provide command to run E2E tests
        Write-Host "`nTo run end-to-end tests, use:" -ForegroundColor Cyan
        $e2eParams = @()
        if ($RestApiUrl) {
            $e2eParams += "-RestApiUrl `"$RestApiUrl`""
        } elseif ($RestApiId) {
            $region = if ($Region) { $Region } else { "us-east-1" }  # Default to us-east-1 if not specified
            $apiUrl = "https://$RestApiId.execute-api.$region.amazonaws.com/$Stage"
            $e2eParams += "-RestApiUrl `"$apiUrl`""
        }
        
        if ($WebSocketUrl) {
            $e2eParams += "-WebSocketUrl `"$WebSocketUrl`""
        } elseif ($WebSocketApiId) {
            $region = if ($Region) { $Region } else { "us-east-1" }  # Default to us-east-1 if not specified
            $wsUrl = "wss://$WebSocketApiId.execute-api.$region.amazonaws.com/$Stage"
            $e2eParams += "-WebSocketUrl `"$wsUrl`""
        }
        
        Write-Host ".\backend\scripts\test_e2e.ps1 $($e2eParams -join ' ')" -ForegroundColor Yellow
    } else {
        Write-Host "CloudWatch logging configuration failed. Check output for details." -ForegroundColor Red
    }
}

# Function to run selected action
function Run-Action {
    param ([string]$SelectedAction)
    
    switch ($SelectedAction) {
        "1" {
            # Test REST API Gateway
            if (-not $RestApiUrl) {
                $RestApiUrl = Read-Host "Enter REST API Gateway URL"
            }
            
            $params = @("-ApiUrl", $RestApiUrl)
            if ($Username -and $Password) {
                $params += @("-Username", $Username, "-Password", $Password)
            }
            
            Write-Host "Running REST API Gateway Tests..." -ForegroundColor Cyan
            & $testApiScript @params
        }
        
        "2" {
            # Test WebSocket API Gateway
            if (-not $WebSocketUrl) {
                $WebSocketUrl = Read-Host "Enter WebSocket API Gateway URL"
            }
            
            $params = @("-WebSocketUrl", $WebSocketUrl)
            if ($Username -and $Password) {
                # If we have both username and password but no access token, let's get one
                $script:accessToken = $null
                if ($RestApiUrl) {
                    Write-Host "Getting authentication token..." -ForegroundColor Gray
                    $authUrl = "$RestApiUrl/api/auth/login"
                    $authBody = @{
                        email = $Username
                        password = $Password
                    } | ConvertTo-Json
                    
                    try {
                        $authResponse = Invoke-RestMethod -Uri $authUrl -Method Post -Body $authBody -ContentType "application/json"
                        $script:accessToken = $authResponse.data.access_token
                        Write-Host "Successfully obtained authentication token" -ForegroundColor Gray
                    } catch {
                        Write-Warning "Failed to get authentication token. WebSocket test will run without authentication."
                    }
                }
                
                if ($script:accessToken) {
                    $params += @("-AuthToken", $script:accessToken)
                }
            }
            
            Write-Host "Running WebSocket API Gateway Tests..." -ForegroundColor Cyan
            & $testWebSocketScript @params
        }
        
        "3" {
            # Run End-to-End Tests
            $params = @()
            
            if ($RestApiUrl) {
                $params += @("-RestApiUrl", $RestApiUrl)
            }
            
            if ($WebSocketUrl) {
                $params += @("-WebSocketUrl", $WebSocketUrl)
            }
            
            if ($FrontendUrl) {
                $params += @("-FrontendUrl", $FrontendUrl)
            }
            
            if ($Username -and $Password) {
                $params += @("-Username", $Username, "-Password", $Password)
            }
            
            Write-Host "Running End-to-End Tests..." -ForegroundColor Cyan
            & $testE2eScript @params
        }
        
        "4" {
            # Configure API Gateway Logging
            if (-not $pythonInstalled) {
                Write-Host "Python is not installed or not in PATH. Please install Python 3.7+" -ForegroundColor Red
                return
            }
            
            if (-not (Test-Path $configureLoggingScript)) {
                Write-Error "Configuration script not found: $configureLoggingScript"
                return
            }
            
            if (-not $RestApiId -and -not $WebSocketApiId) {
                $apiType = Read-Host "Configure logging for which API type? (1: REST, 2: WebSocket, 3: Both)"
                
                if ($apiType -eq "1" -or $apiType -eq "3") {
                    $RestApiId = Read-Host "Enter REST API Gateway ID"
                }
                
                if ($apiType -eq "2" -or $apiType -eq "3") {
                    $WebSocketApiId = Read-Host "Enter WebSocket API Gateway ID"
                }
                
                $Stage = Read-Host "Enter API Gateway stage (default: prod)"
                if (-not $Stage) {
                    $Stage = "prod"
                }
            }
            
            $params = @("--stage", $Stage)
            
            if ($RestApiId) {
                $params += @("--rest-api-id", $RestApiId)
            }
            
            if ($WebSocketApiId) {
                $params += @("--ws-api-id", $WebSocketApiId)
            }
            
            Write-Host "Configuring API Gateway Logging..." -ForegroundColor Cyan
            & python $configureLoggingScript @params
        }
        
        "5" {
            # Monitor API Gateway Logs
            if (-not $pythonInstalled) {
                Write-Host "Python is not installed or not in PATH. Please install Python 3.7+" -ForegroundColor Red
                return
            }
            
            if (-not (Test-Path $monitorLogsScript)) {
                Write-Error "Monitoring script not found: $monitorLogsScript"
                return
            }
            
            $apiType = Read-Host "Monitor logs for which API type? (1: REST, 2: WebSocket)"
            $apiId = $null
            $isWebSocket = $false
            
            if ($apiType -eq "1") {
                if (-not $RestApiId) {
                    $apiId = Read-Host "Enter REST API Gateway ID"
                } else {
                    $apiId = $RestApiId
                }
            } elseif ($apiType -eq "2") {
                if (-not $WebSocketApiId) {
                    $apiId = Read-Host "Enter WebSocket API Gateway ID"
                } else {
                    $apiId = $WebSocketApiId
                }
                $isWebSocket = $true
            } else {
                Write-Error "Invalid API type selection"
                return
            }
            
            if (-not $Stage) {
                $Stage = Read-Host "Enter API Gateway stage (default: prod)"
                if (-not $Stage) {
                    $Stage = "prod"
                }
            }
            
            $follow = Read-Host "Follow logs in real-time? (y/n)"
            $filter = Read-Host "Log filter pattern (optional)"
            $outputFile = Read-Host "Output file path (optional)"
            
            $params = @("--api-id", $apiId, "--stage", $Stage)
            
            if ($isWebSocket) {
                $params += "--ws"
            }
            
            if ($follow -eq "y") {
                $params += "--follow"
            }
            
            if ($filter) {
                $params += @("--filter", $filter)
            }
            
            if ($outputFile) {
                $params += @("--output", $outputFile)
            }
            
            Write-Host "Monitoring API Gateway Logs..." -ForegroundColor Cyan
            & python $monitorLogsScript @params
        }
        
        "6" {
            # Install AWS Dependencies
            Install-AwsDependencies
        }
        
        "7" {
            # Auto-Configure CloudWatch Logging
            Auto-ConfigureLogging
        }
        
        "auto" {
            # Auto-Configure CloudWatch Logging (alias for 7)
            Auto-ConfigureLogging
        }
        
        default {
            if ($SelectedAction -ne "Q" -and $SelectedAction -ne "q") {
                Write-Host "Invalid option. Please try again." -ForegroundColor Red
            }
        }
    }
}

# Handle -Auto switch parameter
if ($Auto) {
    $Action = "auto"
}

# Main execution flow
if ($Action -eq "menu") {
    # Interactive menu mode
    do {
        Show-Menu
        $selection = Read-Host "Please make a selection"
        if ($selection -ne "Q" -and $selection -ne "q") {
            Run-Action -SelectedAction $selection
            Write-Host "`nPress any key to continue..." -ForegroundColor Yellow
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    } until ($selection -eq "Q" -or $selection -eq "q")
} else {
    # Direct action mode
    Run-Action -SelectedAction $Action
}

Write-Host "Exiting..." -ForegroundColor Cyan 