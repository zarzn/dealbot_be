#!/usr/bin/env pwsh

# AI Agentic Deals System - Service Tests Runner
Write-Host "🚀 Starting AI Agentic Deals System Service Tests" -ForegroundColor Cyan

# Configuration with absolute paths
$BACKEND_ROOT = "C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend"
$TEST_ROOT = "$BACKEND_ROOT\backend_tests"
$RESULTS_DIR = "$BACKEND_ROOT\scripts\test_results"
$PATCH_FILE = "$BACKEND_ROOT\patch_settings.py"

# Display paths for debugging
Write-Host "Using the following paths:" -ForegroundColor Yellow
Write-Host "BACKEND_ROOT: $BACKEND_ROOT" -ForegroundColor Yellow
Write-Host "TEST_ROOT: $TEST_ROOT" -ForegroundColor Yellow
Write-Host "RESULTS_DIR: $RESULTS_DIR" -ForegroundColor Yellow
Write-Host "PATCH_FILE: $PATCH_FILE" -ForegroundColor Yellow

# Set environment variables for Redis
$env:REDIS_URL = "redis://localhost:6379/0"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_DB = "0"
$env:REDIS_PASSWORD = ""
$env:host = "localhost"
$env:hosts = '["localhost"]'

# Create results directory if it doesn't exist
if (-not (Test-Path $RESULTS_DIR)) {
    New-Item -ItemType Directory -Path $RESULTS_DIR -Force | Out-Null
    Write-Host "Created results directory: $RESULTS_DIR" -ForegroundColor Green
}

# Check if patch_settings.py exists
if (-not (Test-Path $PATCH_FILE)) {
    Write-Host "Error: patch_settings.py file not found at $PATCH_FILE" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Found patch_settings.py at $PATCH_FILE" -ForegroundColor Green
}

# Check if test directory exists
if (-not (Test-Path $TEST_ROOT)) {
    Write-Host "Error: Test directory not found at $TEST_ROOT" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Found test directory at $TEST_ROOT" -ForegroundColor Green
}

# Main execution
try {
    Write-Host "`n========== Running Service Tests ==========" -ForegroundColor Cyan
    
    # Set environment variable to use test environment
    $env:USE_TEST_ENV = "true"
    
    # Create a temporary Python script to run the tests with patched settings
    $tempScriptPath = "$env:TEMP\run_service_tests.py"
    
    @"
import sys
import os

# Add the project root to the Python path
backend_root = r'$BACKEND_ROOT'
sys.path.insert(0, backend_root)

# Import the patch_settings module to override the settings
patch_settings_path = r'$PATCH_FILE'
print(f"Loading patch settings from: {patch_settings_path}")

import importlib.util
spec = importlib.util.spec_from_file_location('patch_settings', patch_settings_path)
patch_settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch_settings)

# Import pytest and run the tests
import pytest
test_path = r'$TEST_ROOT'
results_dir = r'$RESULTS_DIR'
print(f"Running tests from: {test_path}")
print(f"Saving results to: {results_dir}")
print(f"Using marker: service")

exit_code = pytest.main([
    test_path, 
    '-v', 
    '-m', 'service', 
    '-k', 'not integration and not feature',
    '--html='+os.path.join(results_dir, 'service_report.html'), 
    '--self-contained-html',
    '--timeout=60'  # Add timeout for individual tests
])

sys.exit(exit_code)
"@ | Out-File -FilePath $tempScriptPath -Encoding utf8
    
    # Run the Python script directly in the current terminal
    Write-Host "Running tests with script: $tempScriptPath" -ForegroundColor Yellow
    
    try {
        # Run Python directly without opening a new window and capture output
        Write-Host "Running service tests..." -ForegroundColor Cyan
        
        # First, remove any existing report to ensure a fresh one is created
        $reportFile = "$RESULTS_DIR\service_report.html"
        if (Test-Path $reportFile) {
            Remove-Item -Path $reportFile -Force
        }
        
        # Run the tests directly (not using Start-Process)
        python $tempScriptPath
        $exitCode = $LASTEXITCODE
    }
    catch {
        Write-Host "Error running tests: $_" -ForegroundColor Red
        $exitCode = 99
    }
    
    # Remove the temporary script
    Remove-Item -Path $tempScriptPath -Force -ErrorAction SilentlyContinue
    
    # Create a summary file to track results
    $summaryFile = "$RESULTS_DIR\service_test_summary.txt"
    "# Service Test Results Summary" | Out-File -FilePath $summaryFile -Force
    "" | Out-File -FilePath $summaryFile -Append
    "Generated: $(Get-Date)" | Out-File -FilePath $summaryFile -Append
    "" | Out-File -FilePath $summaryFile -Append
    
    # Record result in summary
    if ($exitCode -eq 0) {
        Write-Host "Service tests completed successfully" -ForegroundColor Green
        "✅ Service tests: PASSED" | Out-File -FilePath $summaryFile -Append
    } else {
        Write-Host "Service tests had failures" -ForegroundColor Yellow
        "❌ Service tests: FAILED or had issues" | Out-File -FilePath $summaryFile -Append
    }
    
    # List all generated HTML reports
    "" | Out-File -FilePath $summaryFile -Append
    "## Generated Reports:" | Out-File -FilePath $summaryFile -Append
    $reportFile = "$RESULTS_DIR\service_report.html"
    if (Test-Path $reportFile) {
        "- service_report.html" | Out-File -FilePath $summaryFile -Append
    } else {
        "No report file was generated." | Out-File -FilePath $summaryFile -Append
    }
    
    Write-Host "`nTest execution complete. Summary saved to $summaryFile" -ForegroundColor Cyan
    Write-Host "To view the report, open the HTML file in the results directory:" -ForegroundColor Cyan
    Write-Host "$RESULTS_DIR\service_report.html" -ForegroundColor Yellow
    
    exit $exitCode
}
catch {
    Write-Host "Error running tests: $_" -ForegroundColor Red
    exit 1
} 