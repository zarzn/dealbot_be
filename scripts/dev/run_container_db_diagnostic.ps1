# PowerShell script to run simplified database diagnostics inside Docker container
param (
    [int]$Duration = 60,
    [int]$Interval = 5
)

Write-Host "Running simplified database connection diagnostics in Docker container..." -ForegroundColor Cyan

# Get the container ID for the running backend container - one container at a time
$containerId = docker ps --filter "name=deals_backend" --filter "status=running" --format "{{.ID}}" | Select-Object -First 1

if (-not $containerId) {
    Write-Host "Could not find container 'deals_backend', trying alternative names..." -ForegroundColor Yellow
    
    # Try with alternative name patterns
    $containerNames = @("backend", "agentic-deals-backend")
    
    foreach ($name in $containerNames) {
        Write-Host "Trying with container name '$name'..." -ForegroundColor Yellow
        $containerId = docker ps --filter "name=$name" --filter "status=running" --format "{{.ID}}" | Select-Object -First 1
        
        if ($containerId) {
            Write-Host "Found container with name containing '$name'" -ForegroundColor Green
            break
        }
    }
    
    if (-not $containerId) {
        Write-Host "Error: Could not find a running backend container." -ForegroundColor Red
        Write-Host "Available containers:" -ForegroundColor Yellow
        docker ps
        exit 1
    }
}

Write-Host "Found container ID: $containerId" -ForegroundColor Green

# Copy the diagnostics script to the container
Write-Host "Copying diagnostics script to container..." -ForegroundColor Cyan
docker cp "$PSScriptRoot/container_db_diagnostic.py" "${containerId}:/app/scripts/container_db_diagnostic.py"

# Run the diagnostics script inside the container
Write-Host "Running diagnostics inside container (duration: ${Duration}s, interval: ${Interval}s)..." -ForegroundColor Green
docker exec $containerId python /app/scripts/container_db_diagnostic.py $Duration $Interval

Write-Host "Diagnostics completed." -ForegroundColor Cyan
