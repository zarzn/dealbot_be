# Update FastAPI Application CORS Configuration
# This script updates the CORS configuration in the FastAPI application code

param(
    [Parameter(Mandatory=$false)]
    [string]$AppFile = "../../core/api/app.py",
    
    [Parameter(Mandatory=$false)]
    [string[]]$AllowedOrigins = @("https://d3irpl0o2ddv9y.cloudfront.net"),
    
    [Parameter(Mandatory=$false)]
    [switch]$ForceUpdate = $false
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to display colored output
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    else {
        $input | Write-Output
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success($message) {
    Write-ColorOutput Green "[SUCCESS] $message"
}

function Write-Info($message) {
    Write-ColorOutput Cyan "[INFO] $message"
}

function Write-Warning($message) {
    Write-ColorOutput Yellow "[WARNING] $message"
}

function Write-Error($message) {
    Write-ColorOutput Red "[ERROR] $message"
}

# Function to check if the app file exists
function Test-AppFile {
    param (
        [string]$AppFile
    )
    
    if (-not (Test-Path $AppFile)) {
        Write-Error "FastAPI application file not found at: $AppFile"
        return $false
    }
    
    Write-Success "FastAPI application file found at: $AppFile"
    return $true
}

# Function to update CORS configuration in the FastAPI app file
function Update-AppCors {
    param (
        [string]$AppFile,
        [string[]]$AllowedOrigins,
        [switch]$ForceUpdate
    )
    
    try {
        # Read the app file
        $appContent = Get-Content $AppFile -Raw
        
        # Format the allowed origins as a Python list
        $originsArray = $AllowedOrigins | ForEach-Object { "`"$_`"" }
        $originsString = $originsArray -join ", "
        $originsListString = "[$originsString]"
        
        # Check if CORSMiddleware is already configured
        if ($appContent -match "CORSMiddleware\(.*?allow_origins\s*=\s*\[(.*?)\]") {
            $currentOrigins = $Matches[1]
            
            if ($currentOrigins -eq $originsString) {
                Write-Info "CORS allow_origins is already set to: $currentOrigins"
                
                if ($ForceUpdate) {
                    Write-Info "Force update is enabled. Updating anyway."
                }
                else {
                    Write-Info "No changes needed. Use -ForceUpdate to update anyway."
                    return $true
                }
            }
            else {
                Write-Info "Current CORS allow_origins: $currentOrigins"
                Write-Info "New CORS allow_origins: $originsString"
            }
            
            # Update the existing CORS configuration
            $newAppContent = $appContent -replace "(CORSMiddleware\(.*?allow_origins\s*=\s*\[).*?(\])", "`$1$originsString`$2"
            
            # Write the updated content back to the file
            $newAppContent | Set-Content $AppFile
            
            Write-Success "Updated CORS allow_origins in FastAPI app to: $originsString"
        }
        else {
            # CORS middleware not found, add it
            Write-Info "CORS middleware not found in the app file. Adding it."
            
            # Find the app creation line
            if ($appContent -match "app\s*=\s*FastAPI\(") {
                # Add CORS middleware after app creation
                $corsMiddleware = @"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=$originsListString,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"@
                
                # Check if we need to add the import
                if (-not ($appContent -match "from fastapi.middleware.cors import CORSMiddleware")) {
                    $corsImport = "from fastapi.middleware.cors import CORSMiddleware"
                    
                    # Find the imports section
                    if ($appContent -match "from fastapi import .*") {
                        $newAppContent = $appContent -replace "(from fastapi import .*)", "`$1`n$corsImport"
                    }
                    else {
                        # Add import at the top of the file
                        $newAppContent = "$corsImport`n$appContent"
                    }
                    
                    $appContent = $newAppContent
                }
                
                # Add the middleware after app creation
                $newAppContent = $appContent -replace "(app\s*=\s*FastAPI\(.*?\))", "`$1$corsMiddleware"
                
                # Write the updated content back to the file
                $newAppContent | Set-Content $AppFile
                
                Write-Success "Added CORS middleware to FastAPI app with allow_origins: $originsString"
            }
            else {
                Write-Error "Could not find FastAPI app creation in the file. CORS middleware not added."
                return $false
            }
        }
        
        return $true
    }
    catch {
        Write-Error "Failed to update CORS configuration in FastAPI app: $_"
        return $false
    }
}

# Main function
function Update-FastApiAppCors {
    Write-Info "Starting FastAPI application CORS configuration update..."
    Write-Info "Application file: $AppFile"
    Write-Info "Allowed origins: $($AllowedOrigins -join ', ')"
    
    # Check if the app file exists
    if (-not (Test-AppFile -AppFile $AppFile)) {
        return $false
    }
    
    # Update CORS configuration in the app file
    if (-not (Update-AppCors -AppFile $AppFile -AllowedOrigins $AllowedOrigins -ForceUpdate:$ForceUpdate)) {
        return $false
    }
    
    Write-Success "FastAPI application CORS configuration updated successfully."
    Write-Info "Note: You need to restart the FastAPI application for changes to take effect."
    return $true
}

# Run the main function
Update-FastApiAppCors 