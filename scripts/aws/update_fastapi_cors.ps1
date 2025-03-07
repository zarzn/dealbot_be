# Update FastAPI CORS Configuration
# This script updates the CORS configuration in the .env file for the FastAPI application

param(
    [Parameter(Mandatory=$false)]
    [string]$EnvFile = "../../.env",
    
    [Parameter(Mandatory=$false)]
    [string[]]$AllowedOrigins = @("https://d3irpl0o2ddv9y.cloudfront.net", "https://rebaton.ai"),
    
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

# Function to check if the .env file exists
function Test-EnvFile {
    param (
        [string]$EnvFile
    )
    
    if (-not (Test-Path $EnvFile)) {
        Write-Error "Environment file not found at: $EnvFile"
        return $false
    }
    
    Write-Success "Environment file found at: $EnvFile"
    return $true
}

# Function to update CORS configuration in .env file
function Update-EnvCors {
    param (
        [string]$EnvFile,
        [string[]]$AllowedOrigins,
        [switch]$ForceUpdate
    )
    
    try {
        # Read the .env file
        $envContent = Get-Content $EnvFile -Raw
        
        # Format the allowed origins as a comma-separated string
        $originsString = $AllowedOrigins -join ","
        
        # Check if CORS_ORIGINS already exists in the .env file
        if ($envContent -match "CORS_ORIGINS=(.*)") {
            $currentOrigins = $Matches[1]
            
            if ($currentOrigins -eq $originsString) {
                Write-Info "CORS_ORIGINS is already set to: $currentOrigins"
                
                if ($ForceUpdate) {
                    Write-Info "Force update is enabled. Updating anyway."
                }
                else {
                    Write-Info "No changes needed. Use -ForceUpdate to update anyway."
                    return $true
                }
            }
            else {
                Write-Info "Current CORS_ORIGINS: $currentOrigins"
                Write-Info "New CORS_ORIGINS: $originsString"
            }
            
            # Update the existing CORS_ORIGINS
            $envContent = $envContent -replace "CORS_ORIGINS=(.*)", "CORS_ORIGINS=$originsString"
        }
        else {
            # Add CORS_ORIGINS if it doesn't exist
            Write-Info "CORS_ORIGINS not found in .env file. Adding it."
            
            if ($envContent.EndsWith("`n")) {
                $envContent += "CORS_ORIGINS=$originsString"
            }
            else {
                $envContent += "`nCORS_ORIGINS=$originsString"
            }
        }
        
        # Write the updated content back to the .env file
        $envContent | Set-Content $EnvFile
        
        Write-Success "Updated CORS_ORIGINS in .env file to: $originsString"
        return $true
    }
    catch {
        Write-Error "Failed to update CORS configuration in .env file: $_"
        return $false
    }
}

# Main function
function Update-FastApiCors {
    Write-Info "Starting FastAPI CORS configuration update..."
    Write-Info "Environment file: $EnvFile"
    Write-Info "Allowed origins: $($AllowedOrigins -join ', ')"
    
    # Check if the .env file exists
    if (-not (Test-EnvFile -EnvFile $EnvFile)) {
        return $false
    }
    
    # Update CORS configuration in .env file
    if (-not (Update-EnvCors -EnvFile $EnvFile -AllowedOrigins $AllowedOrigins -ForceUpdate:$ForceUpdate)) {
        return $false
    }
    
    Write-Success "FastAPI CORS configuration updated successfully."
    Write-Info "Note: You need to restart the FastAPI application for changes to take effect."
    return $true
}

# Run the main function
Update-FastApiCors 