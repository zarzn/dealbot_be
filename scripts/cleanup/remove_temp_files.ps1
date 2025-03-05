#!/usr/bin/env pwsh
# Script to find and remove temporary and backup files from the codebase

param (
    [switch]$ListOnly = $false,
    [string]$RootDir = ".",
    [switch]$Help = $false
)

function Show-Help {
    Write-Host "Remove Temporary Files Script"
    Write-Host "------------------------------"
    Write-Host "This script finds and optionally removes temporary/backup files from the codebase."
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -ListOnly     Only list files without removing them (default: true)"
    Write-Host "  -RootDir      Root directory to search (default: current directory)"
    Write-Host "  -Help         Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  ./remove_temp_files.ps1 -ListOnly              # List all temporary files"
    Write-Host "  ./remove_temp_files.ps1 -RootDir 'C:/Projects' # Remove temp files from specified directory"
    Write-Host "  ./remove_temp_files.ps1                        # Remove all temporary files from current directory"
    exit 0
}

# Show help if requested
if ($Help) {
    Show-Help
}

# Patterns for temporary and backup files
$tempPatterns = @(
    "*.bak",
    "*.tmp",
    "*~",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "*.pyc",
    "__pycache__",
    "*.orig",
    "*.log",
    "*.rej",
    ".#*",
    "Thumbs.db",
    "desktop.ini",
    "*.old",
    "*.backup"
)

# Additional patterns specifically for Python projects
$pythonPatterns = @(
    ".coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".pytype",
    ".ipynb_checkpoints",
    "*.py[cod]",
    "*$py.class"
)

# Combine all patterns
$allPatterns = $tempPatterns + $pythonPatterns

# Convert root directory to absolute path
$RootDir = Resolve-Path $RootDir

# Find all temporary files recursively
$tempFiles = @()
foreach ($pattern in $allPatterns) {
    # Skip directories in the search pattern to handle them separately
    if ($pattern -ne "__pycache__" -and $pattern -ne ".pytest_cache" -and 
        $pattern -ne ".mypy_cache" -and $pattern -ne ".pytype" -and 
        $pattern -ne ".ipynb_checkpoints") {
        $found = Get-ChildItem -Path $RootDir -Filter $pattern -File -Recurse -Force -ErrorAction SilentlyContinue
        $tempFiles += $found
    }
}

# Find directories that match our patterns
$tempDirs = @()
$dirPatterns = @("__pycache__", ".pytest_cache", ".mypy_cache", ".pytype", ".ipynb_checkpoints")
foreach ($pattern in $dirPatterns) {
    $found = Get-ChildItem -Path $RootDir -Directory -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq $pattern }
    $tempDirs += $found
}

# Exclude directories that should not be processed
$excludeDirs = @(".git", ".github", "venv", "env", ".venv", "node_modules")
$tempFiles = $tempFiles | Where-Object { 
    $shouldInclude = $true
    foreach ($dir in $excludeDirs) {
        if ($_.FullName -like "*\$dir\*") {
            $shouldInclude = $false
            break
        }
    }
    $shouldInclude
}

$tempDirs = $tempDirs | Where-Object { 
    $shouldInclude = $true
    foreach ($dir in $excludeDirs) {
        if ($_.FullName -like "*\$dir\*") {
            $shouldInclude = $false
            break
        }
    }
    $shouldInclude
}

# Display what we found
Write-Host "Found $($tempFiles.Count) temporary files and $($tempDirs.Count) temporary directories."

if ($tempFiles.Count -gt 0 -or $tempDirs.Count -gt 0) {
    # Show files
    if ($tempFiles.Count -gt 0) {
        Write-Host "`nTemporary Files:" -ForegroundColor Yellow
        foreach ($file in $tempFiles) {
            $relativePath = $file.FullName.Substring($RootDir.Path.Length + 1)
            Write-Host "  $relativePath"
        }
    }
    
    # Show directories
    if ($tempDirs.Count -gt 0) {
        Write-Host "`nTemporary Directories:" -ForegroundColor Yellow
        foreach ($dir in $tempDirs) {
            $relativePath = $dir.FullName.Substring($RootDir.Path.Length + 1)
            Write-Host "  $relativePath"
        }
    }
    
    # If not in list-only mode, ask for confirmation to delete
    if (-not $ListOnly) {
        $confirmation = Read-Host "`nDo you want to remove these temporary files and directories? (y/N)"
        if ($confirmation -eq 'y' -or $confirmation -eq 'Y') {
            # Remove files
            foreach ($file in $tempFiles) {
                try {
                    Remove-Item $file.FullName -Force
                    Write-Host "Removed file: $($file.FullName)" -ForegroundColor Green
                } catch {
                    Write-Host "Failed to remove file: $($file.FullName)" -ForegroundColor Red
                    Write-Host $_.Exception.Message
                }
            }
            
            # Remove directories
            foreach ($dir in $tempDirs) {
                try {
                    Remove-Item $dir.FullName -Recurse -Force
                    Write-Host "Removed directory: $($dir.FullName)" -ForegroundColor Green
                } catch {
                    Write-Host "Failed to remove directory: $($dir.FullName)" -ForegroundColor Red
                    Write-Host $_.Exception.Message
                }
            }
            
            Write-Host "`nCleanup completed!" -ForegroundColor Green
        } else {
            Write-Host "`nOperation cancelled. No files were removed." -ForegroundColor Yellow
        }
    } else {
        Write-Host "`nList-only mode. No files were removed." -ForegroundColor Cyan
        Write-Host "Run without -ListOnly to remove the files." -ForegroundColor Cyan
    }
} else {
    Write-Host "No temporary files found in the specified directory." -ForegroundColor Green
} 