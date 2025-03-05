#!/usr/bin/env pwsh

# AI Agentic Deals System - Complete Test Suite Runner
Write-Host "🚀 Starting AI Agentic Deals System Complete Test Suite" -ForegroundColor Cyan

# Configuration with absolute paths
$BACKEND_ROOT = "C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend"
$SCRIPTS_DIR = "$BACKEND_ROOT\scripts\dev\test"
$RESULTS_DIR = "$BACKEND_ROOT\scripts\test_results"

# Display paths for debugging
Write-Host "Using the following paths:" -ForegroundColor Yellow
Write-Host "BACKEND_ROOT: $BACKEND_ROOT" -ForegroundColor Yellow
Write-Host "SCRIPTS_DIR: $SCRIPTS_DIR" -ForegroundColor Yellow
Write-Host "RESULTS_DIR: $RESULTS_DIR" -ForegroundColor Yellow

# Test categories with their scripts and dependencies
$TEST_CATEGORIES = [ordered]@{
    "Core" = @{
        "script" = "$SCRIPTS_DIR\run_core_tests.ps1"
        "depends_on" = @()  # Core tests have no dependencies
    }
    "Service" = @{
        "script" = "$SCRIPTS_DIR\run_service_tests.ps1"
        "depends_on" = @("Core")  # Service tests depend on Core tests
    }
    "Feature" = @{
        "script" = "$SCRIPTS_DIR\run_feature_tests.ps1"
        "depends_on" = @("Core", "Service")  # Feature tests depend on Core and Service tests
    }
    "Integration" = @{
        "script" = "$SCRIPTS_DIR\run_integration_tests.ps1"
        "depends_on" = @("Core", "Service", "Feature")  # Integration tests depend on all other tests
    }
}

# Create results directory if it doesn't exist
if (-not (Test-Path $RESULTS_DIR)) {
    New-Item -ItemType Directory -Path $RESULTS_DIR -Force | Out-Null
    Write-Host "Created results directory: $RESULTS_DIR" -ForegroundColor Green
}

# Initialize category status tracking
$categoryStatus = @{}

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
        if (-not $categoryStatus.ContainsKey($dependency) -or $categoryStatus[$dependency] -eq $false) {
            Write-Host "Dependency $dependency not executed successfully yet" -ForegroundColor Yellow
            return $false
        }
    }
    
    # All dependencies were executed successfully
    return $true
}

# Main execution
try {
    # Create a summary file to track results
    $summaryFile = "$RESULTS_DIR\all_tests_summary.txt"
    "# Complete Test Suite Results Summary" | Out-File -FilePath $summaryFile -Force
    "" | Out-File -FilePath $summaryFile -Append
    "Generated: $(Get-Date)" | Out-File -FilePath $summaryFile -Append
    "" | Out-File -FilePath $summaryFile -Append
    
    # Run tests for each category in order
    foreach ($category in $TEST_CATEGORIES.Keys) {
        $categoryInfo = $TEST_CATEGORIES[$category]
        $scriptPath = $categoryInfo.script
        $dependencies = $categoryInfo.depends_on
        
        # Check if script exists
        if (-not (Test-Path $scriptPath)) {
            Write-Host "Error: Script not found at $scriptPath" -ForegroundColor Red
            "⚠️ $category tests: SKIPPED (script not found: $scriptPath)" | Out-File -FilePath $summaryFile -Append
            continue
        }
        
        # Check if dependencies are met
        $dependenciesMet = Can-RunCategory -Category $category -Dependencies $dependencies
        
        if ($dependenciesMet) {
            # Run tests only if dependencies are met
            Write-Host "`n========== Running $category Tests ==========" -ForegroundColor Cyan
            
            try {
                # Run the script
                & $scriptPath
                $exitCode = $LASTEXITCODE
                
                # Record result
                if ($exitCode -eq 0) {
                    Write-Host "$category tests completed successfully" -ForegroundColor Green
                    "✅ $category tests: PASSED" | Out-File -FilePath $summaryFile -Append
                    $categoryStatus[$category] = $true
                } else {
                    Write-Host "$category tests had failures but we're continuing to the next category" -ForegroundColor Yellow
                    "❌ $category tests: FAILED or had issues" | Out-File -FilePath $summaryFile -Append
                    $categoryStatus[$category] = $false
                }
            }
            catch {
                Write-Host "Error running $category tests: $_" -ForegroundColor Red
                "⚠️ $category tests: ERROR during execution" | Out-File -FilePath $summaryFile -Append
                $categoryStatus[$category] = $false
            }
        } else {
            # Skip tests if dependencies are not met
            $dependenciesList = $dependencies -join ", "
            Write-Host "Skipping $category tests: dependencies not met ($dependenciesList)" -ForegroundColor Yellow
            "⏩ $category tests: SKIPPED (dependencies not met: $dependenciesList)" | Out-File -FilePath $summaryFile -Append
            $categoryStatus[$category] = $false
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
    Write-Host "To view reports, open the HTML files in the results directory:" -ForegroundColor Cyan
    Write-Host $RESULTS_DIR -ForegroundColor Yellow
    exit 0
}
catch {
    Write-Host "Error running tests: $_" -ForegroundColor Red
    exit 1
} 