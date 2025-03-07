# Run search functionality tests
# This script runs the search functionality tests and analyzes the results

# Set the environment variables for testing
$env:TESTING = "True"
$env:ENVIRONMENT = "test"

Write-Host "Running search functionality tests..." -ForegroundColor Green

# Change to the backend directory
Set-Location $PSScriptRoot\..\..\..

# Activate the virtual environment if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
    Write-Host "Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "Virtual environment not found, continuing without activation" -ForegroundColor Yellow
}

# Run the search functionality tests
Write-Host "Running basic search functionality tests..." -ForegroundColor Cyan
pytest backend_tests/test_search_functionality.py -v

Write-Host "Running detailed search workflow tests..." -ForegroundColor Cyan
pytest backend_tests/test_search_workflow.py -v

# Analyze the test results
Write-Host "`nSearch Functionality Test Analysis" -ForegroundColor Magenta
Write-Host "=================================" -ForegroundColor Magenta

# Check if any tests failed
$testResults = $LASTEXITCODE
if ($testResults -eq 0) {
    Write-Host "All search tests passed successfully!" -ForegroundColor Green
} else {
    Write-Host "Some search tests failed. Please review the test output above." -ForegroundColor Red
}

# Provide additional analysis
Write-Host "`nSearch Workflow Analysis:" -ForegroundColor Yellow
Write-Host "1. The tests verify that the search endpoint correctly processes search parameters."
Write-Host "2. The tests check that the search service correctly constructs database queries."
Write-Host "3. The tests validate error handling for invalid search parameters."
Write-Host "4. The tests ensure that rate limiting is properly applied."

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. If all tests pass, the search functionality is working correctly."
Write-Host "2. If any tests fail, review the specific failure and fix the issue."
Write-Host "3. After fixing issues, run the tests again to verify the fix."

# Return to the original directory
Set-Location $PSScriptRoot

# Return the test result code
exit $testResults 