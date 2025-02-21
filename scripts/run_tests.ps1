#!/usr/bin/env pwsh

# Test Suite Runner Script
Write-Host "🚀 Starting AI Agentic Deals System Test Suite" -ForegroundColor Cyan

# Configuration
$TEST_DIRS = @(
    "test_api",
    "test_agents",
    "test_cache",
    "test_integration",
    "test_models",
    "test_tasks",
    "test_websockets"
)

# Create results directory if it doesn't exist
$RESULTS_DIR = "test_results"
if (-not (Test-Path $RESULTS_DIR)) {
    New-Item -ItemType Directory -Path $RESULTS_DIR | Out-Null
}

# Initialize result arrays
$failedTests = @()
$passedTests = @()
$totalTests = 0
$totalPassed = 0
$totalFailed = 0

# Function to run tests and capture output
function Run-TestDirectory {
    param (
        [string]$directory
    )
    
    Write-Host "`n📁 Running tests in: $directory" -ForegroundColor Yellow
    
    # Run pytest with detailed output
    $testOutput = & python -m pytest "tests/$directory" -v --tb=short --junitxml="$RESULTS_DIR/$directory-results.xml" 2>&1
    
    # Parse the output
    $testOutput | ForEach-Object {
        $line = $_
        if ($line -match "FAILED") {
            Write-Host $line -ForegroundColor Red
            $failedTests += $line
        }
        elseif ($line -match "PASSED") {
            Write-Host $line -ForegroundColor Green
            $passedTests += $line
        }
        else {
            Write-Host $line
        }
    }
    
    return $testOutput
}

# Function to generate HTML report
function Generate-HTMLReport {
    param (
        [array]$results
    )
    
    $reportPath = "$RESULTS_DIR/test_report.html"
    $reportContent = @"
<!DOCTYPE html>
<html>
<head>
    <title>Test Suite Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .test-section { margin: 20px 0; }
        .passed { color: green; }
        .failed { color: red; }
        .test-details { margin-left: 20px; }
        pre { background-color: #f8f9fa; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Agentic Deals System Test Results</h1>
        <p>Generated: $(Get-Date)</p>
    </div>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Tests: $totalTests</p>
        <p>Passed: <span class="passed">$totalPassed</span></p>
        <p>Failed: <span class="failed">$totalFailed</span></p>
    </div>
"@

    foreach ($dir in $TEST_DIRS) {
        $reportContent += @"
    <div class="test-section">
        <h2>$dir Results</h2>
        <div class="test-details">
            <pre>$($results[$dir])</pre>
        </div>
    </div>
"@
    }

    $reportContent += @"
</body>
</html>
"@

    $reportContent | Out-File -FilePath $reportPath -Encoding UTF8
    Write-Host "`n📊 HTML Report generated at: $reportPath" -ForegroundColor Cyan
}

# Main execution
try {
    # Change to backend directory
    Set-Location backend
    
    # Store results for each directory
    $results = @{}
    
    # Run tests for each directory
    foreach ($dir in $TEST_DIRS) {
        $results[$dir] = Run-TestDirectory $dir
        
        # Update counters
        $dirResults = $results[$dir] | Select-String -Pattern "(PASSED|FAILED)"
        $totalTests += $dirResults.Count
        $totalPassed += ($dirResults | Where-Object { $_ -match "PASSED" }).Count
        $totalFailed += ($dirResults | Where-Object { $_ -match "FAILED" }).Count
    }
    
    # Run individual test files in root
    $rootTests = @(
        "test_scraper_api.py",
        "test_register.py",
        "test_notifications.py",
        "test_price_integration.py"
    )
    
    foreach ($test in $rootTests) {
        Write-Host "`n📄 Running test: $test" -ForegroundColor Yellow
        $results[$test] = & python -m pytest "tests/$test" -v --tb=short --junitxml="$RESULTS_DIR/$test-results.xml" 2>&1
        
        # Update counters
        $testResults = $results[$test] | Select-String -Pattern "(PASSED|FAILED)"
        $totalTests += $testResults.Count
        $totalPassed += ($testResults | Where-Object { $_ -match "PASSED" }).Count
        $totalFailed += ($testResults | Where-Object { $_ -match "FAILED" }).Count
    }
    
    # Generate report
    Generate-HTMLReport $results
    
    # Print summary
    Write-Host "`n📊 Test Suite Summary:" -ForegroundColor Cyan
    Write-Host "Total Tests: $totalTests" -ForegroundColor White
    Write-Host "Passed: $totalPassed" -ForegroundColor Green
    Write-Host "Failed: $totalFailed" -ForegroundColor Red
    
    # List failed tests if any
    if ($failedTests.Count -gt 0) {
        Write-Host "`n❌ Failed Tests:" -ForegroundColor Red
        $failedTests | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Red
        }
    }
    
    # Return to original directory
    Set-Location ..
    
    # Exit with appropriate code
    exit $totalFailed
}
catch {
    Write-Host "❌ Error running tests: $_" -ForegroundColor Red
    exit 1
} 