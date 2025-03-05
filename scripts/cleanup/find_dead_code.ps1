#!/usr/bin/env pwsh
# Script to find dead code in Python files using vulture

param (
    [switch]$Fix = $false,
    [string]$RootDir = ".",
    [int]$Confidence = 60,
    [string[]]$ExcludeDirs = @("venv", "env", ".venv", "node_modules", ".git", ".github", "__pycache__"),
    [string]$WhitelistFile = "",
    [switch]$Help = $false
)

function Show-Help {
    Write-Host "Find Dead Code Script"
    Write-Host "---------------------"
    Write-Host "This script finds potentially unused code in Python files using vulture."
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -Fix            Generate a comprehensive report with comments (default: false)"
    Write-Host "  -RootDir        Root directory to search (default: current directory)"
    Write-Host "  -Confidence     Minimum confidence level (0-100) for reporting (default: 60)"
    Write-Host "  -ExcludeDirs    Directories to exclude (default: venv,env,.venv,node_modules,.git,.github,__pycache__)"
    Write-Host "  -WhitelistFile  File containing whitelisted items to ignore (optional)"
    Write-Host "  -Help           Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  ./find_dead_code.ps1                       # Find dead code with default settings"
    Write-Host "  ./find_dead_code.ps1 -Fix                  # Generate an annotated report with removal suggestions"
    Write-Host "  ./find_dead_code.ps1 -Confidence 80        # Only show results with high confidence"
    Write-Host "  ./find_dead_code.ps1 -RootDir 'backend'    # Check only backend directory"
    exit 0
}

# Show help if requested
if ($Help) {
    Show-Help
}

# Check if vulture is installed
try {
    $vultureVersion = python -m pip freeze | Select-String "vulture"
    if (-not $vultureVersion) {
        Write-Host "vulture is not installed. Installing now..." -ForegroundColor Yellow
        python -m pip install vulture
    }
} catch {
    Write-Host "Error checking for vulture: $_" -ForegroundColor Red
    Write-Host "Please install vulture: 'pip install vulture'" -ForegroundColor Red
    exit 1
}

# Convert root directory to absolute path
$RootDir = Resolve-Path $RootDir

# Prepare exclude directories
$excludeArgs = @()
foreach ($dir in $ExcludeDirs) {
    $excludeArgs += "--exclude"
    $excludeArgs += $dir
}

# Prepare whitelist argument
$whitelistArgs = @()
if ($WhitelistFile -and (Test-Path $WhitelistFile)) {
    $whitelistArgs = @("--whitelist", $WhitelistFile)
}

# Run vulture on the codebase
Write-Host "Running vulture to find dead code in $RootDir..." -ForegroundColor Cyan
Write-Host "Using minimum confidence level of $Confidence%..." -ForegroundColor Cyan

$vultureArgs = @(
    "-m", "vulture",
    $RootDir,
    "--min-confidence", $Confidence,
    "--sort-by-size"
)

$vultureArgs += $excludeArgs
$vultureArgs += $whitelistArgs

$output = & python $vultureArgs 2>&1

# Parse output
$deadCodeItems = @()
$pattern = "(?<file>[^:]+):(?<line>\d+): (?<message>.+) \((?<confidence>\d+)% confidence\)"

foreach ($line in $output) {
    if ($line -match $pattern) {
        # Extract type from the message
        $itemType = "unknown"
        if ($Matches['message'] -match "^unused (class|function|method|property|variable|import|attribute)") {
            $itemType = $Matches[1]
        }
        
        # Extract name from the message if available
        $itemName = ""
        if ($Matches['message'] -match "^unused [^:]+: '([^']+)'") {
            $itemName = $Matches[1]
        }
        
        $item = @{
            File = $Matches['file']
            Line = $Matches['line']
            Message = $Matches['message']
            Confidence = $Matches['confidence']
            Type = $itemType
            Name = $itemName
        }
        
        # Check if the file is in the project directory
        $fullPath = Join-Path -Path $RootDir -ChildPath $item.File
        if (Test-Path $fullPath) {
            $deadCodeItems += $item
        }
    }
}

# Group by file
$fileGroups = $deadCodeItems | Group-Object -Property File

# Display results
if ($deadCodeItems.Count -gt 0) {
    Write-Host "`nDead Code Report:" -ForegroundColor Yellow
    Write-Host "================" -ForegroundColor Yellow
    
    foreach ($group in $fileGroups | Sort-Object -Property Name) {
        Write-Host "`n$($group.Name)" -ForegroundColor Cyan
        foreach ($item in $group.Group | Sort-Object -Property Line) {
            $confidenceColor = if ([int]$item.Confidence -gt 80) { "Red" } elseif ([int]$item.Confidence -gt 60) { "Yellow" } else { "DarkYellow" }
            Write-Host "  Line $($item.Line): $($item.Message) ($($item.Confidence)% confidence)" -ForegroundColor $confidenceColor
        }
    }
    
    # Summarize by type
    $typeSummary = $deadCodeItems | Group-Object -Property Type | Sort-Object -Property Count -Descending
    
    Write-Host "`nSummary by Type:" -ForegroundColor Cyan
    foreach ($type in $typeSummary) {
        Write-Host "  $($type.Name): $($type.Count) items" -ForegroundColor Cyan
    }
    
    Write-Host "`nTotal dead code items found: $($deadCodeItems.Count)" -ForegroundColor Yellow
    
    # Generate a detailed report if requested
    if ($Fix) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $reportFile = "dead_code_report_$timestamp.md"
        $reportPath = Join-Path -Path $RootDir -ChildPath $reportFile
        
        # Create the report file
        Set-Content -Path $reportPath -Value "# Dead Code Report"
        Add-Content -Path $reportPath -Value "Generated on $(Get-Date)"
        Add-Content -Path $reportPath -Value ""
        
        Add-Content -Path $reportPath -Value "## Overview"
        Add-Content -Path $reportPath -Value "- Total dead code items: $($deadCodeItems.Count)"
        Add-Content -Path $reportPath -Value "- Files affected: $($fileGroups.Count)"
        Add-Content -Path $reportPath -Value "- Confidence threshold: $Confidence%"
        Add-Content -Path $reportPath -Value ""
        
        Add-Content -Path $reportPath -Value "## Summary by Type"
        foreach ($type in $typeSummary) {
            Add-Content -Path $reportPath -Value "- $($type.Name): $($type.Count) items"
        }
        Add-Content -Path $reportPath -Value ""
        
        Add-Content -Path $reportPath -Value "## Detailed Findings"
        foreach ($group in $fileGroups | Sort-Object -Property Name) {
            Add-Content -Path $reportPath -Value "### $($group.Name)"
            Add-Content -Path $reportPath -Value ""
            
            foreach ($item in $group.Group | Sort-Object -Property Line) {
                $confidence = $item.Confidence
                $confidenceSymbol = if ([int]$confidence -gt 80) { "🔴" } elseif ([int]$confidence -gt 60) { "🟡" } else { "🟠" }
                
                Add-Content -Path $reportPath -Value "#### $confidenceSymbol Line $($item.Line): $($item.Message)"
                Add-Content -Path $reportPath -Value "- **Type**: $($item.Type)"
                Add-Content -Path $reportPath -Value "- **Confidence**: $confidence%"
                
                # Get the context from the file
                $fullPath = Join-Path -Path $RootDir -ChildPath $group.Name
                if (Test-Path $fullPath) {
                    $fileContent = Get-Content $fullPath
                    $lineNumber = [int]$item.Line
                    
                    # Get context lines (2 before and 2 after)
                    $startLine = [Math]::Max(1, $lineNumber - 2)
                    $endLine = [Math]::Min($fileContent.Length, $lineNumber + 2)
                    
                    Add-Content -Path $reportPath -Value "- **Context**:"
                    Add-Content -Path $reportPath -Value "```python"
                    
                    for ($i = $startLine; $i -le $endLine; $i++) {
                        $prefix = if ($i -eq $lineNumber) { ">" } else { " " }
                        Add-Content -Path $reportPath -Value "$prefix $i: $($fileContent[$i - 1])"
                    }
                    
                    Add-Content -Path $reportPath -Value "```"
                }
                
                # Recommendations
                Add-Content -Path $reportPath -Value "- **Recommendation**:"
                if ([int]$confidence -gt 80) {
                    Add-Content -Path $reportPath -Value "  - High confidence: Consider removing this $($item.Type) as it appears to be unused."
                } elseif ([int]$confidence -gt 60) {
                    Add-Content -Path $reportPath -Value "  - Medium confidence: Review this $($item.Type) to confirm if it's actually unused before removing."
                } else {
                    Add-Content -Path $reportPath -Value "  - Low confidence: Manual inspection needed. This might be a false positive."
                }
                
                Add-Content -Path $reportPath -Value ""
            }
        }
        
        Add-Content -Path $reportPath -Value "## Next Steps"
        Add-Content -Path $reportPath -Value ""
        Add-Content -Path $reportPath -Value "1. Review each item with a critical eye, especially those with lower confidence."
        Add-Content -Path $reportPath -Value "2. Consider creating a whitelist file for false positives."
        Add-Content -Path $reportPath -Value "3. Remove confirmed dead code in small, focused commits."
        Add-Content -Path $reportPath -Value "4. Run comprehensive tests after each removal to ensure functionality is preserved."
        
        Write-Host "`nDetailed report saved to $reportFile" -ForegroundColor Green
    }
}
else {
    Write-Host "`nNo dead code found with confidence >= $Confidence%. Great job!" -ForegroundColor Green
}

# Suggestion to create a whitelist
if ($deadCodeItems.Count -gt 0 -and -not $WhitelistFile) {
    Write-Host "`nTip: If you identified false positives, create a whitelist file to ignore them in future scans:" -ForegroundColor Cyan
    Write-Host "  1. Create a text file with patterns to ignore (e.g., 'example.py:42: unused variable xyz')" -ForegroundColor Cyan
    Write-Host "  2. Run this script with -WhitelistFile 'path/to/whitelist.txt'" -ForegroundColor Cyan
}

# Generate a simple summary report
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryFile = "dead_code_summary_$timestamp.txt"
$summaryPath = Join-Path -Path $RootDir -ChildPath $summaryFile

Set-Content -Path $summaryPath -Value "Dead Code Summary - $timestamp"
Add-Content -Path $summaryPath -Value "============================"
Add-Content -Path $summaryPath -Value ""
Add-Content -Path $summaryPath -Value "Root Directory: $RootDir"
Add-Content -Path $summaryPath -Value "Confidence Threshold: $Confidence%"
Add-Content -Path $summaryPath -Value ""

if ($deadCodeItems.Count -gt 0) {
    Add-Content -Path $summaryPath -Value "Total dead code items found: $($deadCodeItems.Count)"
    Add-Content -Path $summaryPath -Value "Files affected: $($fileGroups.Count)"
    Add-Content -Path $summaryPath -Value ""
    
    Add-Content -Path $summaryPath -Value "Summary by Type:"
    foreach ($type in $typeSummary) {
        Add-Content -Path $summaryPath -Value "  $($type.Name): $($type.Count) items"
    }
    Add-Content -Path $summaryPath -Value ""
    
    Add-Content -Path $summaryPath -Value "Affected Files:"
    foreach ($group in $fileGroups | Sort-Object -Property Name) {
        Add-Content -Path $summaryPath -Value "  $($group.Name) - $($group.Group.Count) items"
    }
}
else {
    Add-Content -Path $summaryPath -Value "No dead code found with confidence >= $Confidence%."
}

Write-Host "`nSummary report saved to $summaryFile" -ForegroundColor Cyan 