# Run tests in correct dependency order

# Add backend directory to PYTHONPATH
$env:PYTHONPATH = "$PWD;$PWD\backend_tests;$env:PYTHONPATH"

# Function to run tests and check result
function Run-TestLevel {
    param (
        [string]$Level,
        [string]$Marker
    )
    Write-Host "`n=== Running $Level Tests ===`n" -ForegroundColor Cyan
    
    # Run tests with specified marker
    pytest backend_tests -v -m $Marker --html=test_results/$Level-report.html
    
    # Check if tests passed
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n❌ $Level tests failed. Stopping test execution.`n" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    
    Write-Host "`n✅ $Level tests passed.`n" -ForegroundColor Green
}

# Create test results directory
if (-not (Test-Path "test_results")) {
    New-Item -ItemType Directory -Path "test_results"
}

# Run tests in order
try {
    # Level 1: Core Tests
    Run-TestLevel "Core" "core"
    
    # Level 2: Service Tests
    Run-TestLevel "Service" "service"
    
    # Level 3: Feature Tests
    Run-TestLevel "Feature" "feature"
    
    # Level 4: Integration Tests
    Run-TestLevel "Integration" "integration"
    
    Write-Host "`n=== All Tests Completed Successfully! ===`n" -ForegroundColor Green
    
    # Generate combined report
    Write-Host "Generating combined test report..." -ForegroundColor Cyan
    pytest backend_tests -v --html=test_results/full-report.html
    
} catch {
    Write-Host "`nError running tests: $_`n" -ForegroundColor Red
    exit 1
} 