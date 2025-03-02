#!/usr/bin/env pwsh

# AI Agentic Deals System - Patched Test Runner
Write-Host "🚀 Starting AI Agentic Deals System Test Suite (Patched Settings)" -ForegroundColor Cyan

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

# Test categories with their markers and dependencies
$TEST_CATEGORIES = [ordered]@{
    "Core" = @{
        "marker" = "core"
        "depends_on" = @()  # Core tests have no dependencies
    }
    "Service" = @{
        "marker" = "service"
        "depends_on" = @("Core")  # Service tests depend on Core tests
    }
    "Integration" = @{
        "marker" = "integration"
        "depends_on" = @("Core", "Service")  # Integration tests depend on Core and Service tests
    }
    "Feature" = @{
        "marker" = "feature"
        "depends_on" = @("Core", "Service", "Integration")  # Feature tests depend on all previous tests
    }
}

# Create results directory if it doesn't exist
if (-not (Test-Path $RESULTS_DIR)) {
    New-Item -ItemType Directory -Path $RESULTS_DIR -Force | Out-Null
    Write-Host "Created results directory: $RESULTS_DIR" -ForegroundColor Green
}

# Initialize result tracking
$totalTests = 0
$totalPassed = 0
$totalFailed = 0
$failedTests = @()
$testResults = @{}
$categoryStatus = @{}
$testCounts = @{}
$totalCollectedTests = 0

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

# Function to count tests for a specific category without running them
function Count-TestsInCategory {
    param (
        [string]$Category,
        [string]$Marker
    )
    
    Write-Host "`n========== Counting $Category Tests ==========" -ForegroundColor Cyan
    
    # Create a temporary Python script to collect the tests
    $tempScriptPath = "$env:TEMP\count_tests_$Category.py"
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

# Import pytest and collect the tests
import pytest
test_path = r'$TEST_ROOT'
print(f"Collecting tests from: {test_path}")
collected = pytest.main(['--collect-only', test_path, '-m', '$Marker', '-v'])
"@ | Out-File -FilePath $tempScriptPath -Encoding utf8
    
    # Run the temporary script
    $output = & python $tempScriptPath
    
    # Remove the temporary script
    Remove-Item -Path $tempScriptPath -Force
    
    # Count the tests
    $count = 0
    $output | ForEach-Object {
        $line = $_
        if ($line -match "collected (\d+) item") {
            $count = [int]$matches[1]
            Write-Host "Found $count tests in category $Category" -ForegroundColor Green
        }
    }
    
    return $count
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
sys.exit(pytest.main([test_path, '-v', '-m', '$Marker', '--html='+os.path.join(results_dir, '${Category}_report.html'), '--self-contained-html']))
"@ | Out-File -FilePath $tempScriptPath -Encoding utf8
    
    # Run the temporary script
    Write-Host "Running tests with script: $tempScriptPath" -ForegroundColor Yellow
    $output = & python $tempScriptPath
    $exitCode = $LASTEXITCODE
    
    # Remove the temporary script
    Remove-Item -Path $tempScriptPath -Force
    
    # Store the raw output
    $testResults[$Category] = $output
    
    # Parse the output
    $passed = 0
    $failed = 0
    
    $output | ForEach-Object {
        $line = $_
        if ($line -match "FAILED") {
            Write-Host $line -ForegroundColor Red
            $failedTests += $line
            $failed++
        }
        elseif ($line -match "PASSED") {
            Write-Host $line -ForegroundColor Green
            $passed++
        }
        else {
            Write-Host $line
        }
    }
    
    # Update totals
    $script:totalTests += ($passed + $failed)
    $script:totalPassed += $passed
    $script:totalFailed += $failed
    
    $result = @{
        Passed = $passed
        Failed = $failed
        Total = ($passed + $failed)
        Success = ($failed -eq 0)  # True if no tests failed
        ExitCode = $exitCode
    }
    
    # Set the category status
    $script:categoryStatus[$Category] = $result.Success
    
    return $result
}

# Function to check if a test category can run based on dependencies
function Can-RunCategory {
    param (
        [string]$Category,
        [array]$Dependencies
    )
    
    foreach ($dependency in $Dependencies) {
        if (-not $categoryStatus.ContainsKey($dependency) -or -not $categoryStatus[$dependency]) {
            return $false
        }
    }
    
    return $true
}

# Function to generate HTML report
function Generate-HtmlReport {
    param (
        [hashtable]$Results
    )
    
    $htmlReportPath = "$RESULTS_DIR\test_report.html"
    $html = @"
<!DOCTYPE html>
<html>
<head>
    <title>Test Results Summary</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .summary { margin-bottom: 20px; }
        .category { margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .category h2 { margin-top: 0; }
        .passed { color: green; }
        .failed { color: red; }
        .skipped { color: orange; }
        .total { color: blue; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
    </style>
</head>
<body>
    <h1>Test Results Summary</h1>
    
    <div class="summary">
        <h2>Overall Summary</h2>
        <p><span class="total">Total Tests in Codebase: $($script:totalCollectedTests)</span></p>
        <p><span class="total">Tests Executed: $($Results.TotalTests)</span></p>
        <p><span class="passed">Passed Tests: $($Results.TotalPassed)</span></p>
        <p><span class="failed">Failed Tests: $($Results.TotalFailed)</span></p>
        <p><span class="skipped">Skipped Tests: $($Results.TotalSkipped)</span></p>
    </div>
    
    <h2>Test Counts by Category</h2>
    <table>
        <tr>
            <th>Category</th>
            <th>Total Tests in Category</th>
            <th>% of All Tests</th>
        </tr>
"@

    foreach ($category in $script:testCounts.Keys) {
        $categoryCount = $script:testCounts[$category]
        $percentage = [math]::Round(($categoryCount / $script:totalCollectedTests) * 100, 1)
        
        $html += @"
        <tr>
            <td>$category</td>
            <td>$categoryCount</td>
            <td>$percentage%</td>
        </tr>
"@
    }

    $html += @"
    </table>
    
    <h2>Results by Category</h2>
    <table>
        <tr>
            <th>Category</th>
            <th>Total Tests Run</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Status</th>
            <th>Dependency Status</th>
        </tr>
"@

    foreach ($category in $Results.Categories.Keys) {
        $categoryResults = $Results.Categories[$category]
        $status = if ($categoryResults.Failed -eq 0) { "Passed" } else { "Failed" }
        $dependencyStatus = if ($categoryResults.DependenciesMet) { "Met" } else { "Not Met (Skipped)" }
        
        $html += @"
        <tr>
            <td>$category</td>
            <td>$($categoryResults.Total)</td>
            <td>$($categoryResults.Passed)</td>
            <td>$($categoryResults.Failed)</td>
            <td class="$($status.ToLower())">$status</td>
            <td>$dependencyStatus</td>
        </tr>
"@
    }

    $html += @"
    </table>
    
    <h2>Detailed Reports</h2>
    <ul>
"@

    foreach ($category in $Results.Categories.Keys) {
        $categoryResults = $Results.Categories[$category]
        if ($categoryResults.Total -gt 0) {
            $html += @"
            <li><a href="$($category)_report.html">$category Tests Detailed Report</a></li>
"@
        }
    }

    $html += @"
    </ul>
</body>
</html>
"@

    $html | Out-File -FilePath $htmlReportPath -Encoding utf8
    Write-Host "HTML report generated at: $htmlReportPath" -ForegroundColor Green
}

# Function to create summary file
function Create-SummaryFile {
    param (
        [hashtable]$Results
    )
    
    $summaryPath = "$RESULTS_DIR\test_summary.txt"
    $summary = @"
TEST RESULTS SUMMARY
===================

Overall Summary:
  Total Tests in Codebase: $($script:totalCollectedTests)
  Tests Executed: $($Results.TotalTests)
  Passed Tests: $($Results.TotalPassed)
  Failed Tests: $($Results.TotalFailed)
  Skipped Tests: $($Results.TotalSkipped)

Test Counts by Category:
"@

    foreach ($category in $script:testCounts.Keys) {
        $categoryCount = $script:testCounts[$category]
        $percentage = [math]::Round(($categoryCount / $script:totalCollectedTests) * 100, 1)
        
        $summary += @"

  ${category} Tests: $categoryCount tests ($percentage% of total)
"@
    }

    $summary += @"

Results by Category:
"@

    foreach ($category in $Results.Categories.Keys) {
        $categoryResults = $Results.Categories[$category]
        $status = if ($categoryResults.Failed -eq 0) { "Passed" } else { "Failed" }
        $dependencyStatus = if ($categoryResults.DependenciesMet) { "Dependencies Met" } else { "Dependencies Not Met (Skipped)" }
        
        $summary += @"

$category Tests:
  Total Tests in Category: $($script:testCounts[$category])
  Tests Run: $($categoryResults.Total)
  Passed: $($categoryResults.Passed)
  Failed: $($categoryResults.Failed)
  Status: $status
  Dependency Status: $dependencyStatus
"@
    }

    if ($failedTests.Count -gt 0) {
        $summary += @"

Failed Tests:
$($failedTests -join "`n")
"@
    }

    $summary | Out-File -FilePath $summaryPath -Encoding utf8
    Write-Host "Summary file created at: $summaryPath" -ForegroundColor Green
}

# Main execution
try {
    # First, count all tests in each category without running them
    Write-Host "`n========== Counting Tests in All Categories ==========" -ForegroundColor Cyan
    
    foreach ($category in $TEST_CATEGORIES.Keys) {
        $categoryInfo = $TEST_CATEGORIES[$category]
        $marker = $categoryInfo.marker
        
        $count = Count-TestsInCategory -Category $category -Marker $marker
        $script:testCounts[$category] = $count
        $script:totalCollectedTests += $count
    }
    
    Write-Host "`nTotal Tests in All Categories: $totalCollectedTests" -ForegroundColor Cyan
    
    foreach ($category in $script:testCounts.Keys) {
        $categoryCount = $script:testCounts[$category]
        $percentage = [math]::Round(($categoryCount / $script:totalCollectedTests) * 100, 1)
        Write-Host "  ${category} Tests: $categoryCount tests ($percentage% of total)" -ForegroundColor White
    }
    
    # Store results for each category
    $CategoryResults = @{}
    $totalSkipped = 0
    
    # Initialize all category statuses as false
    foreach ($category in $TEST_CATEGORIES.Keys) {
        $categoryStatus[$category] = $false
    }
    
    # Run tests for each category in order
    foreach ($category in $TEST_CATEGORIES.Keys) {
        $categoryInfo = $TEST_CATEGORIES[$category]
        $marker = $categoryInfo.marker
        $dependencies = $categoryInfo.depends_on
        
        # Check if dependencies are met
        $dependenciesMet = Can-RunCategory -Category $category -Dependencies $dependencies
        
        $result = @{
            Passed = 0
            Failed = 0
            Total = 0
            Success = $false
            DependenciesMet = $dependenciesMet
        }
        
        if ($dependenciesMet) {
            # Run tests only if dependencies are met
            $result = Run-TestCategory -Category $category -Marker $marker
            $result.DependenciesMet = $true
        } else {
            # Skip tests if dependencies are not met
            $dependenciesList = $dependencies -join ", "
            Write-Host "`n========== Skipping $category Tests ==========" -ForegroundColor Yellow
            Write-Host "Dependencies not met: $dependenciesList" -ForegroundColor Yellow
            $totalSkipped += 1
            $result.DependenciesMet = $false
        }
        
        $CategoryResults[$category] = $result
    }
    
    # Prepare results for reporting
    $testResults = @{
        "TotalTests" = $totalTests
        "TotalPassed" = $totalPassed
        "TotalFailed" = $totalFailed
        "TotalSkipped" = $totalSkipped
        "Categories" = $CategoryResults
    }
    
    # Generate reports
    Generate-HtmlReport -Results $testResults
    Create-SummaryFile -Results $testResults
    
    # Print final summary
    Write-Host "`n========== TEST EXECUTION COMPLETE ==========" -ForegroundColor Cyan
    Write-Host "Total Tests in Codebase: $totalCollectedTests" -ForegroundColor Cyan
    Write-Host "Tests Executed: $totalTests" -ForegroundColor White
    Write-Host "Passed: $totalPassed" -ForegroundColor Green
    Write-Host "Failed: $totalFailed" -ForegroundColor Red
    Write-Host "Skipped: $totalSkipped" -ForegroundColor Yellow
    Write-Host "`nDetailed HTML report: $RESULTS_DIR\test_report.html" -ForegroundColor Cyan
    Write-Host "Summary file: $RESULTS_DIR\test_summary.txt" -ForegroundColor Cyan
    
    # List failed tests if any
    if ($failedTests.Count -gt 0) {
        Write-Host "`n❌ Failed Tests:" -ForegroundColor Red
        $failedTests | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Red
        }
    }
    
    # Exit with appropriate code
    if ($totalFailed -gt 0) {
        exit 1
    } else {
        exit 0
    }
}
catch {
    Write-Host "❌ Error running tests: $_" -ForegroundColor Red
    exit 1
} 