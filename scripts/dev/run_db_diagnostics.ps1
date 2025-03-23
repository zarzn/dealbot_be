# PowerShell script to run database diagnostics inside Docker container
param (
    [int]$MonitorTime = 60,
    [int]$CheckInterval = 5
)

Write-Host "Running database connection diagnostics in Docker container..." -ForegroundColor Cyan

# Get the container ID for the running backend container
$containerId = docker ps --filter "name=agentic-deals" --format "{{.ID}}"

if (-not $containerId) {
    Write-Host "Error: Could not find a running container with 'agentic-deals' in the name." -ForegroundColor Red
    Write-Host "Make sure your backend container is running." -ForegroundColor Yellow
    exit 1
}

# Copy the diagnostics script to the container
Write-Host "Copying diagnostics script to container..." -ForegroundColor Cyan
docker cp "$PSScriptRoot/diagnose_db_connections.py" "${containerId}:/app/scripts/diagnose_db_connections.py"

# Add execute permissions to the script
docker exec $containerId chmod +x /app/scripts/diagnose_db_connections.py

# Run the diagnostics script inside the container
Write-Host "Running diagnostics inside container (monitor time: ${MonitorTime}s, check interval: ${CheckInterval}s)..." -ForegroundColor Green
docker exec $containerId python /app/scripts/diagnose_db_connections.py --monitor-time=$MonitorTime --check-interval=$CheckInterval

Write-Host "Diagnostics completed." -ForegroundColor Cyan 