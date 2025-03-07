#!/usr/bin/env pwsh

param (
    [switch]$SkipDependencyChecks = $false
)

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

if ($SkipDependencyChecks) {
    Write-Host "Dependency checks are disabled. All test categories will run regardless of dependencies." -ForegroundColor Yellow
}

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
    
    # If dependency checks are disabled, always return true
    if ($SkipDependencyChecks) {
        return $true
    }
    
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
    
    # Create a temporary Python script to generate the main report
    $tempScriptPath = "$env:TEMP\generate_main_report.py"
    
    @"
import sys
import os
import pytest
from datetime import datetime

# Set up paths
results_dir = r'$RESULTS_DIR'
test_reports = [
    os.path.join(results_dir, 'core_report.html'),
    os.path.join(results_dir, 'service_report.html'),
    os.path.join(results_dir, 'feature_report.html'),
    os.path.join(results_dir, 'integration_report.html')
]

# Generate a main report that links to all other reports
main_report = os.path.join(results_dir, 'test_report.html')

# Create HTML content
html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>AI Agentic Deals System Test Reports</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .report-link {{ 
            display: block; 
            margin: 10px 0; 
            padding: 10px; 
            background-color: #f0f0f0; 
            border-radius: 5px;
            text-decoration: none;
            color: #333;
        }}
        .report-link:hover {{ background-color: #e0e0e0; }}
        .timestamp {{ color: #666; font-size: 0.8em; }}
    </style>
</head>
<body>
    <h1>AI Agentic Deals System Test Reports</h1>
    <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Available Test Reports:</h2>
"""

# Add links to individual reports
for report in test_reports:
    if os.path.exists(report):
        report_name = os.path.basename(report)
        last_modified = datetime.fromtimestamp(os.path.getmtime(report)).strftime('%Y-%m-%d %H:%M:%S')
        html_content += f"""    <a href="{report_name}" class="report-link">
        <strong>{report_name}</strong>
        <div class="timestamp">Last updated: {last_modified}</div>
    </a>
"""
    
html_content += """</body>
</html>"""

# Write the HTML file
with open(main_report, 'w') as f:
    f.write(html_content)

print(f"Main report generated at: {main_report}")
"@ | Out-File -FilePath $tempScriptPath -Encoding utf8
    
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
    
    # Generate the main report
    Write-Host "`nGenerating main test report..." -ForegroundColor Cyan
    python $tempScriptPath
    
    # Remove the temporary script
    Remove-Item -Path $tempScriptPath -Force -ErrorAction SilentlyContinue
    
    # List the reports
    $reportFiles = Get-ChildItem -Path $RESULTS_DIR -Filter "*_report.html" -ErrorAction SilentlyContinue
    if ($reportFiles) {
        foreach ($file in $reportFiles) {
            "- $($file.Name)" | Out-File -FilePath $summaryFile -Append
            # Display the last modified time to verify reports are being updated
            $lastModified = $file.LastWriteTime
            "  Last updated: $lastModified" | Out-File -FilePath $summaryFile -Append
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