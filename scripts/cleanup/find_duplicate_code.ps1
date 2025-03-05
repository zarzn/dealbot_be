#!/usr/bin/env pwsh
# Script to find duplicate code in Python files using pylint

param (
    [string]$RootDir = ".",
    [int]$MinimumSimilarity = 95,
    [string[]]$ExcludeDirs = @("venv", "env", ".venv", "node_modules", ".git", ".github", "__pycache__"),
    [switch]$Help = $false
)

function Show-Help {
    Write-Host "Find Duplicate Code Script"
    Write-Host "--------------------------"
    Write-Host "This script finds duplicate code in Python files using pylint's similarity checker."
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -RootDir            Root directory to search (default: current directory)"
    Write-Host "  -MinimumSimilarity  Minimum similarity percentage to report (default: 95)"
    Write-Host "  -ExcludeDirs        Directories to exclude (default: venv,env,.venv,node_modules,.git,.github,__pycache__)"
    Write-Host "  -Help               Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  ./find_duplicate_code.ps1                      # Find duplicate code with default settings"
    Write-Host "  ./find_duplicate_code.ps1 -MinimumSimilarity 90 # Lower the similarity threshold"
    Write-Host "  ./find_duplicate_code.ps1 -RootDir 'backend'    # Check only backend directory"
    exit 0
}

# Show help if requested
if ($Help) {
    Show-Help
}

# Check if pylint is installed
try {
    $pylintVersion = python -m pip freeze | Select-String "pylint"
    if (-not $pylintVersion) {
        Write-Host "pylint is not installed. Installing now..." -ForegroundColor Yellow
        python -m pip install pylint
    }
} catch {
    Write-Host "Error checking for pylint: $_" -ForegroundColor Red
    Write-Host "Please install pylint: 'pip install pylint'" -ForegroundColor Red
    exit 1
}

# Convert root directory to absolute path
$RootDir = Resolve-Path $RootDir

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

$fileCount = $pyFiles.Count
Write-Host "Found $fileCount Python files to check." -ForegroundColor Cyan

if ($fileCount -eq 0) {
    Write-Host "No Python files found in the specified directory." -ForegroundColor Yellow
    exit 0
}

# Create a temporary file with the list of files to check
$tempFile = [System.IO.Path]::GetTempFileName()
$pyFiles.FullName | Out-File -FilePath $tempFile

# Run pylint's similarity checker
Write-Host "Running pylint similarity checker with minimum similarity of $MinimumSimilarity%..." -ForegroundColor Cyan
$output = python -m pylint.checkers.similar --min-similarity-lines=5 --ignore-comments=yes --ignore-docstrings=yes --ignore-imports=yes --ignore-signatures=yes --similarity-threshold=$MinimumSimilarity --files-output=$tempFile 2>&1

# Parse the output
$duplicateBlocks = @()
$currentBlock = $null
$blockPattern = "^Similar lines in (\d+) files"
$filePattern = "^(.*?):(\d+)-(\d+)$"

foreach ($line in $output) {
    if ($line -match $blockPattern) {
        # Start of a new block
        if ($currentBlock) {
            $duplicateBlocks += $currentBlock
        }
        
        $currentBlock = @{
            FileCount = [int]$Matches[1]
            Files = @()
            Lines = @()
        }
    }
    elseif ($line -match $filePattern -and $currentBlock) {
        # File information
        $currentBlock.Files += $Matches[1]
        $currentBlock.Lines += "$($Matches[2])-$($Matches[3])"
    }
    elseif ($line -and $currentBlock -and $line -notmatch "^\s*$") {
        # Code content
        if (-not $currentBlock.ContainsKey("Code")) {
            $currentBlock.Code = @()
        }
        $currentBlock.Code += $line
    }
}

# Add the last block if it exists
if ($currentBlock) {
    $duplicateBlocks += $currentBlock
}

# Clean up the temporary file
Remove-Item -Path $tempFile -Force

# Display results
if ($duplicateBlocks.Count -gt 0) {
    Write-Host "`nDuplicate Code Report:" -ForegroundColor Yellow
    Write-Host "=====================" -ForegroundColor Yellow
    
    $totalDuplicateBlocks = $duplicateBlocks.Count
    $totalDuplicateFiles = ($duplicateBlocks | ForEach-Object { $_.Files } | Sort-Object -Unique).Count
    $totalDuplicateLines = ($duplicateBlocks | ForEach-Object { $_.Code.Count * $_.FileCount } | Measure-Object -Sum).Sum
    
    Write-Host "Found $totalDuplicateBlocks duplicate code blocks across $totalDuplicateFiles files ($totalDuplicateLines lines)." -ForegroundColor Yellow
    
    foreach ($block in $duplicateBlocks) {
        Write-Host "`nDuplicate Block (${MinimumSimilarity}%+ similarity) found in $($block.FileCount) files:" -ForegroundColor Cyan
        
        for ($i = 0; $i -lt $block.Files.Count; $i++) {
            Write-Host "  $($block.Files[$i]):$($block.Lines[$i])" -ForegroundColor White
        }
        
        Write-Host "`nDuplicated Code:" -ForegroundColor Magenta
        Write-Host "```python" -ForegroundColor Gray
        foreach ($line in $block.Code) {
            Write-Host "  $line" -ForegroundColor Gray
        }
        Write-Host "```" -ForegroundColor Gray
    }
    
    # Generate a report file
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportFile = "duplicate_code_report_$timestamp.md"
    $reportPath = Join-Path -Path $RootDir -ChildPath $reportFile
    
    Set-Content -Path $reportPath -Value "# Duplicate Code Report"
    Add-Content -Path $reportPath -Value "Generated on $(Get-Date)"
    Add-Content -Path $reportPath -Value ""
    
    Add-Content -Path $reportPath -Value "## Summary"
    Add-Content -Path $reportPath -Value "- Total duplicate blocks: $totalDuplicateBlocks"
    Add-Content -Path $reportPath -Value "- Files with duplicates: $totalDuplicateFiles"
    Add-Content -Path $reportPath -Value "- Total duplicate lines: $totalDuplicateLines"
    Add-Content -Path $reportPath -Value "- Minimum similarity threshold: $MinimumSimilarity%"
    Add-Content -Path $reportPath -Value ""
    
    Add-Content -Path $reportPath -Value "## Duplicate Blocks"
    
    $blockNumber = 1
    foreach ($block in $duplicateBlocks) {
        Add-Content -Path $reportPath -Value "### Block $blockNumber"
        Add-Content -Path $reportPath -Value "Found in $($block.FileCount) files:"
        Add-Content -Path $reportPath -Value ""
        
        for ($i = 0; $i -lt $block.Files.Count; $i++) {
            Add-Content -Path $reportPath -Value "- $($block.Files[$i]):$($block.Lines[$i])"
        }
        
        Add-Content -Path $reportPath -Value ""
        Add-Content -Path $reportPath -Value "Duplicated Code:"
        Add-Content -Path $reportPath -Value "```python"
        foreach ($line in $block.Code) {
            Add-Content -Path $reportPath -Value $line
        }
        Add-Content -Path $reportPath -Value "```"
        Add-Content -Path $reportPath -Value ""
        
        $blockNumber++
    }
    
    Add-Content -Path $reportPath -Value "## Recommendations"
    Add-Content -Path $reportPath -Value ""
    Add-Content -Path $reportPath -Value "1. **Extract Common Functionality**: Consider refactoring duplicate code into shared functions or classes."
    Add-Content -Path $reportPath -Value "2. **Create Utilities**: For common operations, create utility functions in a central location."
    Add-Content -Path $reportPath -Value "3. **Use Inheritance**: If duplicates are in similar classes, consider using inheritance or mixins."
    Add-Content -Path $reportPath -Value "4. **Apply DRY Principle**: Remember 'Don't Repeat Yourself' - each piece of knowledge should have a single, unambiguous representation."
    
    Write-Host "`nDetailed report saved to $reportFile" -ForegroundColor Green
    
    # Provide some recommendations
    Write-Host "`nRecommendations:" -ForegroundColor Cyan
    Write-Host "1. Extract common functionality into shared functions or classes" -ForegroundColor Cyan
    Write-Host "2. Create utility functions for common operations" -ForegroundColor Cyan
    Write-Host "3. Consider using inheritance or mixins for similar classes" -ForegroundColor Cyan
    Write-Host "4. Apply the DRY (Don't Repeat Yourself) principle" -ForegroundColor Cyan
}
else {
    Write-Host "`nNo duplicate code found with similarity >= $MinimumSimilarity%. Great job!" -ForegroundColor Green
    
    # Generate an empty report
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportFile = "duplicate_code_report_$timestamp.md"
    $reportPath = Join-Path -Path $RootDir -ChildPath $reportFile
    
    Set-Content -Path $reportPath -Value "# Duplicate Code Report"
    Add-Content -Path $reportPath -Value "Generated on $(Get-Date)"
    Add-Content -Path $reportPath -Value ""
    Add-Content -Path $reportPath -Value "No duplicate code found with similarity >= $MinimumSimilarity%."
}

Write-Host "`nReport saved to $reportFile" -ForegroundColor Cyan 