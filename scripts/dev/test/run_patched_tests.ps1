#!/usr/bin/env pwsh

# AI Agentic Deals System - Simplified Test Runner
Write-Host "🚀 Starting AI Agentic Deals System Test Suite (Core and Service tests only)" -ForegroundColor Cyan

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

# Test categories with their markers and dependencies - ONLY Core and Service tests
$TEST_CATEGORIES = [ordered]@{
    "Core" = @{
        "marker" = "core"
        "depends_on" = @()  # Core tests have no dependencies
    }
    "Service" = @{
        "marker" = "service"
        "depends_on" = @("Core")  # Service tests depend on Core tests
    }
}

# Create results directory if it doesn't exist
if (-not (Test-Path $RESULTS_DIR)) {
    New-Item -ItemType Directory -Path $RESULTS_DIR -Force | Out-Null
    Write-Host "Created results directory: $RESULTS_DIR" -ForegroundColor Green
}

# Initialize category status tracking
$categoryStatus = @{}

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

# Function to run tests for a specific category
function Run-TestCategory {
    param (
        [string]$Category,
        [string]$Marker
    )
    
    Write-Host "`n========== Running $Category Tests ==========" -ForegroundColor Cyan
    
    # Set environment variable to use test environment
    $env:USE_TEST_ENV = "true"
    
    # Create a temporary Python script to run the tests with patched settings
    $tempScriptPath = "$env:TEMP\run_tests_$Category.py"
    
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
print(f"Using marker: $Marker")

exit_code = pytest.main([
    test_path, 
    '-v', 
    '-m', '$Marker', 
    '-k', 'not integration and not feature',
    '--html='+os.path.join(results_dir, '${Category}_report.html'), 
    '--self-contained-html',
    '--timeout=60'  # Add timeout for individual tests
])

sys.exit(exit_code)
"@ | Out-File -FilePath $tempScriptPath -Encoding utf8
    
    # Run the Python script with a timeout
    Write-Host "Running tests with script: $tempScriptPath" -ForegroundColor Yellow
    
    try {
        # Run Python with timeout
        $process = Start-Process -FilePath "python" -ArgumentList $tempScriptPath -PassThru
        
        # Wait for up to 5 minutes
        $completed = $process.WaitForExit(300000)
        
        if (-not $completed) {
            Write-Host "Test execution timed out after 5 minutes, forcibly terminating..." -ForegroundColor Red
            $process.Kill()
            $exitCode = 2 # Custom code for timeout
        } else {
            $exitCode = $process.ExitCode
        }
    }
    catch {
        Write-Host "Error running tests: $_" -ForegroundColor Red
        $exitCode = 99
    }
    
    # Remove the temporary script
    Remove-Item -Path $tempScriptPath -Force -ErrorAction SilentlyContinue
    
    # Always mark the category as executed regardless of result
    $script:categoryStatus[$Category] = $true
    
    # Return simple success/failure
    return ($exitCode -eq 0)
}

# Function to check if a test category can run based on dependencies
function Can-RunCategory {
    param (
        [string]$Category,
        [array]$Dependencies
    )
    
    # If no dependencies, can always run
    if ($Dependencies.Count -eq 0) {
        return $true
    }
    
    # Check if all dependencies were executed
    foreach ($dependency in $Dependencies) {
        if (-not $categoryStatus.ContainsKey($dependency)) {
            Write-Host "Dependency $dependency not executed yet" -ForegroundColor Yellow
            return $false
        }
    }
    
    # All dependencies were executed
    return $true
}

# Main execution
try {
    # Create a summary file to track results
    $summaryFile = "$RESULTS_DIR\test_summary.txt"
    "# Test Results Summary" | Out-File -FilePath $summaryFile -Force
    "" | Out-File -FilePath $summaryFile -Append
    "Generated: $(Get-Date)" | Out-File -FilePath $summaryFile -Append
    "" | Out-File -FilePath $summaryFile -Append
    "**Note: Only running Core and Service tests. Integration and Feature tests excluded.**" | Out-File -FilePath $summaryFile -Append
    "" | Out-File -FilePath $summaryFile -Append
    
    # Run tests for each category in order
    foreach ($category in $TEST_CATEGORIES.Keys) {
        $categoryInfo = $TEST_CATEGORIES[$category]
        $marker = $categoryInfo.marker
        $dependencies = $categoryInfo.depends_on
        
        # Check if dependencies are met
        $dependenciesMet = Can-RunCategory -Category $category -Dependencies $dependencies
        
        if ($dependenciesMet) {
            # Run tests only if dependencies are met
            $success = Run-TestCategory -Category $category -Marker $marker
            
            # Record result in summary
            if ($success) {
                Write-Host "$category tests completed successfully" -ForegroundColor Green
                "✅ $category tests: PASSED" | Out-File -FilePath $summaryFile -Append
            } else {
                Write-Host "$category tests had failures but we're continuing to the next category" -ForegroundColor Yellow
                "❌ $category tests: FAILED or had issues" | Out-File -FilePath $summaryFile -Append
            }
        } else {
            # Skip tests if dependencies are not met
            $dependenciesList = $dependencies -join ", "
            Write-Host "Skipping $category tests: dependencies not met ($dependenciesList)" -ForegroundColor Yellow
            "⏩ $category tests: SKIPPED (dependencies not met: $dependenciesList)" | Out-File -FilePath $summaryFile -Append
        }
    }
    
    # List all generated HTML reports
    "" | Out-File -FilePath $summaryFile -Append
    "## Generated Reports:" | Out-File -FilePath $summaryFile -Append
    $reportFiles = Get-ChildItem -Path $RESULTS_DIR -Filter "*_report.html" -ErrorAction SilentlyContinue
    if ($reportFiles) {
        foreach ($file in $reportFiles) {
            "- $($file.Name)" | Out-File -FilePath $summaryFile -Append
        }
    } else {
        "No report files were generated." | Out-File -FilePath $summaryFile -Append
    }
    
    Write-Host "`nTest execution complete. Summary saved to $summaryFile" -ForegroundColor Cyan
    Write-Host "To view a report, open one of the HTML files in the results directory:" -ForegroundColor Cyan
    Write-Host $RESULTS_DIR -ForegroundColor Yellow
    exit 0
}
catch {
    Write-Host "Error running tests: $_" -ForegroundColor Red
    exit 1
} 