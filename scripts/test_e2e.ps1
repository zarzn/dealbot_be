# End-to-End Testing Script for API Gateways
# This script performs a comprehensive test of frontend-backend integration through API Gateways

param(
    [string]$RestApiUrl = $env:API_GATEWAY_URL,
    [string]$WebSocketUrl = $env:WEBSOCKET_API_GATEWAY_URL,
    [string]$FrontendUrl = $env:NEXT_PUBLIC_APP_URL,
    [string]$Username = "",
    [string]$Password = ""
)

# Function to display test status
function Display-TestStatus {
    param(
        [string]$TestName,
        [bool]$Success,
        [string]$Details = ""
    )
    
    $color = if ($Success) { "Green" } else { "Red" }
    $status = if ($Success) { "✅ PASS" } else { "❌ FAIL" }
    
    Write-Host "[$status] $TestName" -ForegroundColor $color
    if ($Details) {
        Write-Host "  Details: $Details" -ForegroundColor "Gray"
    }
}

# Function to make REST API calls
function Invoke-ApiRequest {
    param(
        [string]$Method = "GET",
        [string]$Endpoint,
        [object]$Body = $null,
        [hashtable]$Headers = @{},
        [switch]$Anonymous
    )
    
    $url = "$RestApiUrl$Endpoint"
    
    if (-not $Anonymous -and $script:accessToken) {
        $Headers["Authorization"] = "Bearer $script:accessToken"
    }
    
    $params = @{
        Method = $Method
        Uri = $url
        Headers = $Headers
        ContentType = "application/json"
        UseBasicParsing = $true
    }
    
    if ($Body -and $Method -ne "GET") {
        $params.Body = (ConvertTo-Json $Body)
    }
    
    try {
        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $statusDescription = $_.Exception.Response.StatusDescription
        $responseBody = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($responseBody)
        $responseContent = $reader.ReadToEnd()
        
        Write-Error "API request failed: $statusCode $statusDescription`n$responseContent"
        return $null
    }
}

# Check that required URLs are provided
if (-not $RestApiUrl) {
    Write-Error "REST API Gateway URL is required. Please provide it as a parameter or set the API_GATEWAY_URL environment variable."
    exit 1
}

if (-not $WebSocketUrl) {
    Write-Warning "WebSocket API Gateway URL not provided. WebSocket tests will be skipped."
}

if (-not $FrontendUrl) {
    Write-Warning "Frontend URL not provided. Frontend-specific tests will be skipped."
}

# Set up temporary directory for websocket test
$tempDir = Join-Path $PSScriptRoot "temp"
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

Write-Host "Starting End-to-End API Integration Tests" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "REST API URL: $RestApiUrl"
if ($WebSocketUrl) { Write-Host "WebSocket URL: $WebSocketUrl" }
if ($FrontendUrl) { Write-Host "Frontend URL: $FrontendUrl" }
Write-Host "----------------------------------------`n" -ForegroundColor Cyan

# Run connection tests to ensure basic connectivity
Write-Host "Phase 1: Basic Connectivity Tests" -ForegroundColor Yellow

# Test 1: Health Check
$healthSuccess = $false
$healthDetails = ""
try {
    $healthResponse = Invoke-ApiRequest -Method "GET" -Endpoint "/health" -Anonymous
    if ($healthResponse -and $healthResponse.status -eq "healthy") {
        $healthSuccess = $true
        $healthDetails = "API is healthy"
    } else {
        $healthDetails = "API health check returned unexpected response"
    }
}
catch {
    $healthDetails = "Health check failed: $_"
}
Display-TestStatus -TestName "API Health Check" -Success $healthSuccess -Details $healthDetails

# Test 2: Frontend Accessibility (if URL provided)
if ($FrontendUrl) {
    $frontendSuccess = $false
    $frontendDetails = ""
    try {
        $frontendResponse = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing
        if ($frontendResponse.StatusCode -eq 200) {
            $frontendSuccess = $true
            $frontendDetails = "Frontend is accessible"
        } else {
            $frontendDetails = "Frontend returned status code: $($frontendResponse.StatusCode)"
        }
    }
    catch {
        $frontendDetails = "Frontend accessibility check failed: $_"
    }
    Display-TestStatus -TestName "Frontend Accessibility" -Success $frontendSuccess -Details $frontendDetails
}

# Test 3: Authentication (if credentials provided)
$script:accessToken = $null
if ($Username -and $Password) {
    Write-Host "`nPhase 2: Authentication Tests" -ForegroundColor Yellow
    
    $authSuccess = $false
    $authDetails = ""
    try {
        $authBody = @{
            email = $Username
            password = $Password
        }
        
        $authResponse = Invoke-ApiRequest -Method "POST" -Endpoint "/api/auth/login" -Body $authBody -Anonymous
        
        if ($authResponse -and $authResponse.data.access_token) {
            $script:accessToken = $authResponse.data.access_token
            $authSuccess = $true
            $authDetails = "Successfully authenticated with the API"
        } else {
            $authDetails = "Authentication response did not contain an access token"
        }
    }
    catch {
        $authDetails = "Authentication failed: $_"
    }
    Display-TestStatus -TestName "API Authentication" -Success $authSuccess -Details $authDetails
    
    # Test 4: User Profile (if authenticated)
    if ($script:accessToken) {
        $profileSuccess = $false
        $profileDetails = ""
        try {
            $profileResponse = Invoke-ApiRequest -Method "GET" -Endpoint "/api/users/me"
            
            if ($profileResponse -and $profileResponse.data.email) {
                $profileSuccess = $true
                $profileDetails = "User profile retrieved successfully: $($profileResponse.data.name) ($($profileResponse.data.email))"
            } else {
                $profileDetails = "User profile response did not contain expected data"
            }
        }
        catch {
            $profileDetails = "User profile retrieval failed: $_"
        }
        Display-TestStatus -TestName "User Profile" -Success $profileSuccess -Details $profileDetails
    }
}

# Test 5: Data Retrieval Tests
Write-Host "`nPhase 3: Data Retrieval Tests" -ForegroundColor Yellow

# Test 5.1: Deals API
$dealsSuccess = $false
$dealsDetails = ""
try {
    $dealsResponse = Invoke-ApiRequest -Method "GET" -Endpoint "/api/deals?limit=5"
    
    if ($dealsResponse -and $dealsResponse.data -ne $null) {
        $dealsSuccess = $true
        $dealsCount = $dealsResponse.data.Count
        $dealsDetails = "Retrieved $dealsCount deals"
        
        if ($dealsCount -gt 0) {
            $sampleDeal = $dealsResponse.data[0]
            $dealsDetails += ". Sample deal: $($sampleDeal.title)"
        }
    } else {
        $dealsDetails = "Deals API response did not contain expected data"
    }
}
catch {
    $dealsDetails = "Deals API request failed: $_"
}
Display-TestStatus -TestName "Deals API" -Success $dealsSuccess -Details $dealsDetails

# Test 5.2: Markets API
$marketsSuccess = $false
$marketsDetails = ""
try {
    $marketsResponse = Invoke-ApiRequest -Method "GET" -Endpoint "/api/markets"
    
    if ($marketsResponse -and $marketsResponse.data -ne $null) {
        $marketsSuccess = $true
        $marketsCount = $marketsResponse.data.Count
        $marketsDetails = "Retrieved $marketsCount markets"
    } else {
        $marketsDetails = "Markets API response did not contain expected data"
    }
}
catch {
    $marketsDetails = "Markets API request failed: $_"
}
Display-TestStatus -TestName "Markets API" -Success $marketsSuccess -Details $marketsDetails

# Test 6: WebSocket Tests (if URL provided)
if ($WebSocketUrl) {
    Write-Host "`nPhase 4: WebSocket Tests" -ForegroundColor Yellow
    
    # Check if Node.js is installed
    $nodeInstalled = $false
    try {
        $nodeVersion = node --version
        $nodeInstalled = $true
    } catch {
        $nodeInstalled = $false
    }
    
    if (-not $nodeInstalled) {
        Write-Warning "Node.js is not installed. Skipping WebSocket tests."
    } else {
        # Create a temporary Node.js script for WebSocket testing
        $wsTestScript = @"
const WebSocket = require('ws');

// Setup connection URL with auth token if provided
const connectionUrl = process.argv[2] + (process.argv[3] ? `?token=\${process.argv[3]}` : '');
console.log(`Connecting to WebSocket at: \${connectionUrl}`);

// Initialize WebSocket connection
const ws = new WebSocket(connectionUrl);
let success = false;
let connectionEstablished = false;
let receivedPong = false;

// Set timeout for the entire test
setTimeout(() => {
  console.log(`RESULT:\${success ? 'SUCCESS' : 'FAILURE'}`);
  process.exit(success ? 0 : 1);
}, 10000);

// Connection event handlers
ws.on('open', function open() {
  console.log('Connection established successfully');
  connectionEstablished = true;
  
  // Send a ping message
  console.log('Sending ping message...');
  ws.send(JSON.stringify({
    action: 'ping',
    data: {},
    requestId: 'ping-' + Date.now()
  }));
});

ws.on('message', function incoming(data) {
  try {
    const message = JSON.parse(data);
    console.log(`Received message: \${message.type}`);
    
    if (message.type === 'pong') {
      console.log('Received pong response!');
      receivedPong = true;
      success = true;
      ws.close();
    }
  } catch (err) {
    console.log(`Error parsing message: \${err.message}`);
  }
});

ws.on('error', function error(err) {
  console.log(`WebSocket error: \${err.message}`);
  process.exit(1);
});

ws.on('close', function close(code, reason) {
  console.log(`Connection closed: \${code} \${reason || 'No reason provided'}`);
  console.log(`RESULT:\${success ? 'SUCCESS' : 'FAILURE'}`);
  process.exit(success ? 0 : 1);
});
"@

        $wsScriptPath = Join-Path $tempDir "websocket-test.js"
        Set-Content -Path $wsScriptPath -Value $wsTestScript
        
        # Check if ws module is installed
        $nodeModulesPath = Join-Path $tempDir "node_modules"
        $wsModulePath = Join-Path $nodeModulesPath "ws"
        
        if (-not (Test-Path $wsModulePath)) {
            Write-Host "Installing WebSocket module..." -ForegroundColor Gray
            
            # Create package.json
            $packageJson = @"
{
  "name": "websocket-tester",
  "version": "1.0.0",
  "description": "WebSocket API tester",
  "dependencies": {
    "ws": "^8.13.0"
  }
}
"@
            $packageJsonPath = Join-Path $tempDir "package.json"
            Set-Content -Path $packageJsonPath -Value $packageJson
            
            # Install dependencies
            Push-Location $tempDir
            npm install --quiet
            Pop-Location
        }
        
        # Run the WebSocket test
        $wsSuccess = $false
        $wsDetails = ""
        try {
            Write-Host "Testing WebSocket connection..." -ForegroundColor Gray
            $wsOutput = node $wsScriptPath $WebSocketUrl $script:accessToken
            
            if ($wsOutput -match "RESULT:SUCCESS") {
                $wsSuccess = $true
                $wsDetails = "WebSocket connection and basic messaging successful"
            } else {
                $wsDetails = "WebSocket test failed. Output: $wsOutput"
            }
        }
        catch {
            $wsDetails = "WebSocket test threw an exception: $_"
        }
        Display-TestStatus -TestName "WebSocket Connection" -Success $wsSuccess -Details $wsDetails
    }
}

# Test 7: API Latency test
Write-Host "`nPhase 5: Performance Tests" -ForegroundColor Yellow

$endpoints = @(
    "/health",
    "/api/deals?limit=1",
    "/api/markets"
)

foreach ($endpoint in $endpoints) {
    $latencySuccess = $false
    $latencyDetails = ""
    $latencyMeasurements = @()
    
    try {
        for ($i = 0; $i -lt 3; $i++) {
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            Invoke-ApiRequest -Method "GET" -Endpoint $endpoint | Out-Null
            $sw.Stop()
            $latencyMeasurements += $sw.ElapsedMilliseconds
        }
        
        $avgLatency = ($latencyMeasurements | Measure-Object -Average).Average
        $maxLatency = 500 # 500ms is acceptable latency for API Gateway
        
        if ($avgLatency -lt $maxLatency) {
            $latencySuccess = $true
            $latencyDetails = "Average latency: $([math]::Round($avgLatency, 2)) ms (acceptable: <$maxLatency ms)"
        } else {
            $latencyDetails = "Average latency: $([math]::Round($avgLatency, 2)) ms (exceeds acceptable: <$maxLatency ms)"
        }
    }
    catch {
        $latencyDetails = "Latency test failed: $_"
    }
    
    Display-TestStatus -TestName "API Latency: $endpoint" -Success $latencySuccess -Details $latencyDetails
}

# Display summary
Write-Host "`nEnd-to-End Testing Complete!" -ForegroundColor Cyan

# Final advice
Write-Host "`nNext Steps for Troubleshooting:" -ForegroundColor Yellow
Write-Host "1. Check API Gateway CloudWatch logs for any errors"
Write-Host "   Run: python backend/scripts/aws/monitor_api_gateway_logs.py --api-id YOUR_API_ID --stage prod"
Write-Host "2. Verify CORS settings in API Gateway if frontend has connection issues"
Write-Host "3. Check Lambda execution logs for backend issues"
Write-Host "4. Verify the frontend environment variables are correctly configured" 