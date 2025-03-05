#!/usr/bin/env pwsh
# Script to find unused imports in Python files using pyflakes

param (
    [switch]$Fix = $false,
    [string]$RootDir = ".",
    [string[]]$ExcludeDirs = @("venv", "env", ".venv", "node_modules", ".git", ".github", "__pycache__"),
    [switch]$Help = $false
)

function Show-Help {
    Write-Host "Find Unused Imports Script"
    Write-Host "--------------------------"
    Write-Host "This script finds unused imports in Python files using pyflakes and optionally removes them using autoflake."
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -Fix           Automatically fix the unused imports (default: false)"
    Write-Host "  -RootDir       Root directory to search (default: current directory)"
    Write-Host "  -ExcludeDirs   Directories to exclude (default: venv,env,.venv,node_modules,.git,.github,__pycache__)"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  ./find_unused_imports.ps1              # Find unused imports without fixing"
    Write-Host "  ./find_unused_imports.ps1 -Fix         # Find and fix unused imports"
    Write-Host "  ./find_unused_imports.ps1 -RootDir 'backend' # Check only backend directory"
    exit 0
}

# Show help if requested
if ($Help) {
    Show-Help
}

# Check if pyflakes is installed
try {
    $pyflakesVersion = python -m pip freeze | Select-String "pyflakes"
    if (-not $pyflakesVersion) {
        Write-Host "pyflakes is not installed. Installing now..." -ForegroundColor Yellow
        python -m pip install pyflakes
    }
} catch {
    Write-Host "Error checking for pyflakes: $_" -ForegroundColor Red
    Write-Host "Please install pyflakes: 'pip install pyflakes'" -ForegroundColor Red
    exit 1
}

# Check if autoflake is installed if we're in fix mode
if ($Fix) {
    try {
        $autoflakeVersion = python -m pip freeze | Select-String "autoflake"
        if (-not $autoflakeVersion) {
            Write-Host "autoflake is not installed. Installing now..." -ForegroundColor Yellow
            python -m pip install autoflake
        }
    } catch {
        Write-Host "Error checking for autoflake: $_" -ForegroundColor Red
        Write-Host "Please install autoflake: 'pip install autoflake'" -ForegroundColor Red
        exit 1
    }
}

# Convert root directory to absolute path
$RootDir = Resolve-Path $RootDir

# Build exclude directory pattern for pyflakes
$excludePattern = ($ExcludeDirs | ForEach-Object { [regex]::Escape($_) }) -join "|"

# Find all Python files
Write-Host "Finding all Python files in $RootDir..." -ForegroundColor Cyan
$pyFiles = Get-ChildItem -Path $RootDir -Filter "*.py" -File -Recurse -Force -ErrorAction SilentlyContinue | 
    Where-Object { 
        $shouldInclude = $true
        foreach ($dir in $ExcludeDirs) {
            if ($_.FullName -like "*\$dir\*") {
                $shouldInclude = $false
                break
            }
        }
        $shouldInclude
    }

Write-Host "Found $($pyFiles.Count) Python files to check." -ForegroundColor Cyan

# Create report structure
$report = @{}
$totalUnusedImports = 0

# Define regex patterns to detect unused imports
$unusedImportPattern = "(?<file>[^:]+):(?<line>\d+):\d+: (F401 '(?<import>[^']+)' imported but unused|'(?<import>[^']+)' imported but unused)"

# Process each Python file with pyflakes
foreach ($file in $pyFiles) {
    $relativePath = $file.FullName.Substring($RootDir.Path.Length + 1)
    Write-Host "Checking $relativePath..." -ForegroundColor Gray -NoNewline
    
    # Run pyflakes on the file
    $output = python -m pyflakes $file.FullName 2>&1
    
    if ($LASTEXITCODE -ne 0 -and $output -match "not found, no module named") {
        Write-Host " ERROR: Module not found" -ForegroundColor Red
        continue
    }
    
    $unusedImports = @()
    
    # Parse the output to find unused imports
    foreach ($line in $output) {
        if ($line -match $unusedImportPattern) {
            $unusedImport = @{
                Line = $Matches['line']
                Import = $Matches['import']
            }
            $unusedImports += $unusedImport
        }
    }
    
    if ($unusedImports.Count -gt 0) {
        Write-Host " Found $($unusedImports.Count) unused imports" -ForegroundColor Yellow
        $report[$relativePath] = $unusedImports
        $totalUnusedImports += $unusedImports.Count
    }
    else {
        Write-Host " OK" -ForegroundColor Green
    }
}

# Display report
if ($totalUnusedImports -gt 0) {
    Write-Host "`nUnused Imports Report:" -ForegroundColor Yellow
    Write-Host "======================" -ForegroundColor Yellow
    
    foreach ($file in $report.Keys | Sort-Object) {
        Write-Host "`n$file" -ForegroundColor Cyan
        foreach ($import in $report[$file]) {
            Write-Host "  Line $($import.Line): '$($import.Import)'" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`nTotal unused imports found: $totalUnusedImports" -ForegroundColor Yellow
    
    # Fix unused imports if requested
    if ($Fix) {
        Write-Host "`nFixing unused imports..." -ForegroundColor Cyan
        $confirmation = Read-Host "Are you sure you want to remove these unused imports? (y/N)"
        
        if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
            foreach ($file in $report.Keys) {
                $fullPath = Join-Path -Path $RootDir -ChildPath $file
                Write-Host "Fixing $file..." -ForegroundColor Cyan
                
                # Use autoflake to remove unused imports
                python -m autoflake --remove-all-unused-imports --in-place $fullPath
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  Fixed unused imports successfully" -ForegroundColor Green
                }
                else {
                    Write-Host "  Failed to fix unused imports" -ForegroundColor Red
                }
            }
            
            Write-Host "`nFixed $totalUnusedImports unused imports in $($report.Keys.Count) files." -ForegroundColor Green
        }
        else {
            Write-Host "`nOperation cancelled. No imports were removed." -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "`nTo fix these issues, run with the -Fix parameter." -ForegroundColor Cyan
    }
}
else {
    Write-Host "`nNo unused imports found. Great job!" -ForegroundColor Green
}

# Generate an output file with the results
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "unused_imports_report_$timestamp.txt"
$reportPath = Join-Path -Path $RootDir -ChildPath $reportFile

"Unused Imports Report - $timestamp" | Out-File -FilePath $reportPath
"=================================" | Out-File -FilePath $reportPath -Append
"" | Out-File -FilePath $reportPath -Append

if ($totalUnusedImports -gt 0) {
    foreach ($file in $report.Keys | Sort-Object) {
        "File: $file" | Out-File -FilePath $reportPath -Append
        foreach ($import in $report[$file]) {
            "  Line $($import.Line): '$($import.Import)'" | Out-File -FilePath $reportPath -Append
        }
        "" | Out-File -FilePath $reportPath -Append
    }
    
    "Total unused imports found: $totalUnusedImports" | Out-File -FilePath $reportPath -Append
}
else {
    "No unused imports found." | Out-File -FilePath $reportPath -Append
}

Write-Host "`nReport saved to $reportFile" -ForegroundColor Cyan 