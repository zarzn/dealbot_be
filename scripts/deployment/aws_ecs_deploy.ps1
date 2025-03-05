#
# AWS ECS Deployment Script for AI Agentic Deals System
# 
# This script automates the process of building, pushing, and deploying
# the backend application to AWS ECS using Fargate.
#

param(
    [string]$ProfileName = "agentic-deals-deployment",
    [string]$Region = "us-east-1",
    [string]$ImageTag = "latest",
    [string]$ClusterName = "agentic-deals-cluster",
    [string]$ServiceName = "agentic-deals-service",
    [string]$TaskDefFile = "../../hardcoded-task-definition.json",
    [string]$ECRRepository = "586794462529.dkr.ecr.us-east-1.amazonaws.com/agentic-deals-backend",
    [switch]$SkipBuild = $false,
    [switch]$SkipPush = $false,
    [switch]$SkipTaskDefUpdate = $false,
    [switch]$ForceNewDeployment = $true
)

$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

function Write-StepHeader {
    param ([string]$Message)
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Test-AwsCliProfile {
    param ([string]$ProfileName)
    
    try {
        $result = aws configure list --profile $ProfileName 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        return $true
    }
    catch {
        return $false
    }
}

# Validate AWS CLI profile
if (-not (Test-AwsCliProfile -ProfileName $ProfileName)) {
    Write-Host "ERROR: AWS CLI profile '$ProfileName' not found or not configured correctly." -ForegroundColor Red
    Write-Host "Please run 'aws configure --profile $ProfileName' to set up the profile." -ForegroundColor Red
    exit 1
}

# Check if current directory contains Dockerfile.prod (only if we're building)
if (-not $SkipBuild) {
    if (-not (Test-Path "Dockerfile.prod")) {
        $rootDir = (Get-Item .).FullName
        if (Test-Path "$rootDir\backend\Dockerfile.prod") {
            Set-Location "$rootDir\backend"
        }
        elseif (Test-Path "$rootDir\..\Dockerfile.prod") {
            Set-Location "$rootDir\.."
        }
        else {
            Write-Host "ERROR: Could not find Dockerfile.prod. Please run this script from the backend directory." -ForegroundColor Red
            exit 1
        }
    }
}

# Check if task definition file exists
if (-not (Test-Path $TaskDefFile)) {
    Write-Host "ERROR: Task definition file '$TaskDefFile' not found." -ForegroundColor Red
    exit 1
}

# Print configuration
Write-StepHeader "Deployment Configuration"
Write-Host "AWS Profile: $ProfileName"
Write-Host "AWS Region: $Region"
Write-Host "Image Tag: $ImageTag"
Write-Host "ECR Repository: $ECRRepository"
Write-Host "ECS Cluster: $ClusterName"
Write-Host "ECS Service: $ServiceName"
Write-Host "Task Definition File: $TaskDefFile"
Write-Host "Skip Build: $SkipBuild"
Write-Host "Skip Push: $SkipPush"
Write-Host "Skip Task Definition Update: $SkipTaskDefUpdate"
Write-Host "Force New Deployment: $ForceNewDeployment"

# Build the Docker image
if (-not $SkipBuild) {
    Write-StepHeader "Building Docker Image"
    docker build -t agentic-deals-backend:$ImageTag -f Dockerfile.prod .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker build failed." -ForegroundColor Red
        exit 1
    }
    
    # Tag the image for ECR
    docker tag "agentic-deals-backend:${ImageTag}" "${ECRRepository}:${ImageTag}"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker tag failed." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Docker image built and tagged successfully." -ForegroundColor Green
}
else {
    Write-Host "Skipping Docker build step..." -ForegroundColor Yellow
}

# Push the image to ECR
if (-not $SkipPush) {
    Write-StepHeader "Pushing Image to ECR"
    
    # Authenticate with ECR
    Write-Host "Authenticating with ECR..."
    aws ecr get-login-password --profile $ProfileName --region $Region | docker login --username AWS --password-stdin $ECRRepository.Split('/')[0]
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: ECR authentication failed." -ForegroundColor Red
        exit 1
    }
    
    # Push the image
    Write-Host "Pushing image to ECR..."
    docker push "${ECRRepository}:${ImageTag}"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker push failed." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Docker image pushed to ECR successfully." -ForegroundColor Green
}
else {
    Write-Host "Skipping Docker push step..." -ForegroundColor Yellow
}

# Register the new task definition
if (-not $SkipTaskDefUpdate) {
    Write-StepHeader "Registering Task Definition"
    
    $taskDefOutputRaw = aws ecs register-task-definition --profile $ProfileName --region $Region --cli-input-json file://$TaskDefFile
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to register task definition." -ForegroundColor Red
        exit 1
    }
    
    # Extract the task definition name and revision
    $taskDefOutput = $taskDefOutputRaw | ConvertFrom-Json
    $taskDefArn = $taskDefOutput.taskDefinition.taskDefinitionArn
    
    if (-not $taskDefArn) {
        Write-Host "ERROR: Failed to extract task definition ARN from output: $taskDefOutputRaw" -ForegroundColor Red
        exit 1
    }
    
    $taskDefParts = $taskDefArn.Split('/')
    if ($taskDefParts.Length -lt 2) {
        Write-Host "ERROR: Invalid task definition ARN format: $taskDefArn" -ForegroundColor Red
        exit 1
    }
    
    $taskDefNameRevision = $taskDefParts[1]
    $taskDefNameRevisionParts = $taskDefNameRevision.Split(':')
    
    if ($taskDefNameRevisionParts.Length -lt 2) {
        Write-Host "ERROR: Invalid task definition name/revision format: $taskDefNameRevision" -ForegroundColor Red
        exit 1
    }
    
    $taskDefName = $taskDefNameRevisionParts[0]
    $taskDefRevision = $taskDefNameRevisionParts[1]
    
    Write-Host "Task definition registered successfully: $taskDefName`:$taskDefRevision" -ForegroundColor Green
    
    # Update the service to use the new task definition
    Write-StepHeader "Updating ECS Service"
    
    if ($ForceNewDeployment) {
        $updateCmd = "aws ecs update-service --profile $ProfileName --region $Region --cluster $ClusterName --service $ServiceName --task-definition $taskDefName`:$taskDefRevision --force-new-deployment"
    }
    else {
        $updateCmd = "aws ecs update-service --profile $ProfileName --region $Region --cluster $ClusterName --service $ServiceName --task-definition $taskDefName`:$taskDefRevision"
    }
    
    Write-Host "Executing: $updateCmd"
    Invoke-Expression "$updateCmd --no-cli-pager"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to update ECS service." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "ECS service updated successfully." -ForegroundColor Green
}
else {
    # Only force a new deployment if not updating the task definition
    if ($ForceNewDeployment) {
        Write-StepHeader "Forcing New Deployment"
        
        $forceCmd = "aws ecs update-service --profile $ProfileName --region $Region --cluster $ClusterName --service $ServiceName --force-new-deployment"
        
        Write-Host "Executing: $forceCmd"
        Invoke-Expression $forceCmd
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to force new deployment." -ForegroundColor Red
            exit 1
        }
        
        Write-Host "Force deployment initiated successfully." -ForegroundColor Green
    }
    else {
        Write-Host "Skipping task definition update and not forcing new deployment..." -ForegroundColor Yellow
    }
}

# Monitor the deployment
Write-StepHeader "Monitoring Deployment"
Write-Host "Waiting for deployment to stabilize..."

$stable = $false
$attempts = 0
$maxAttempts = 30  # 5 minutes (10 second intervals)
$dbConnectionIssue = $false

while (-not $stable -and $attempts -lt $maxAttempts) {
    $attempts++
    
    # Get the service details with no-cli-pager to prevent paging
    $serviceJson = aws ecs describe-services --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --services $ServiceName --query "services[0]" --output json | ConvertFrom-Json
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Failed to get service details. Retrying..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        continue
    }
    
    # Get the latest task ARN with no-cli-pager
    $tasksJson = aws ecs list-tasks --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --service-name $ServiceName --output json | ConvertFrom-Json
    
    if ($tasksJson.taskArns.Count -gt 0) {
        $latestTaskArn = $tasksJson.taskArns[0]
        $taskId = $latestTaskArn.Split('/')[-1]
        
        # Check task status and logs for database connection issues - prevent paging
        $taskDetails = aws ecs describe-tasks --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --tasks $taskId --query "tasks[0]" --output json | ConvertFrom-Json
        $taskStatus = $taskDetails.lastStatus
        
        if ($taskStatus -eq "RUNNING") {
            # Check logs for database connection errors - prevent paging and use temp file to avoid output issues
            $logStreamName = "ecs/agentic-deals-app/$taskId"
            $tempLogFile = [System.IO.Path]::GetTempFileName()
            
            aws logs get-log-events --no-cli-pager --profile $ProfileName --region $Region --log-group-name "/ecs/agentic-deals-container" --log-stream-name $logStreamName --limit 20 --output json | Out-File -FilePath $tempLogFile
            $logs = Get-Content -Path $tempLogFile -Raw | ConvertFrom-Json
            Remove-Item -Path $tempLogFile -Force
            
            foreach ($event in $logs.events) {
                if ($event.message -like "*password authentication failed*" -or $event.message -like "*no pg_hba.conf entry*") {
                    $dbConnectionIssue = $true
                    Write-Host "WARNING: Database connection issue detected in logs." -ForegroundColor Yellow
                    break
                }
            }
            
            if ($dbConnectionIssue) {
                Write-Host "Attempting to fix database connection issue by restarting the task..." -ForegroundColor Yellow
                aws ecs stop-task --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --task $taskId --output json | Out-Null
                $dbConnectionIssue = $false
                $attempts = $attempts - 5  # Give it more time to restart
                Start-Sleep -Seconds 15
                continue
            }
        }
    }
    
    # Check if the service is stable
    if ($serviceJson.deployments.Count -eq 1 -and $serviceJson.runningCount -eq $serviceJson.desiredCount) {
        $stable = $true
    }
    else {
        # Display deployment status
        Write-Host "`rDeployment in progress: Running $($serviceJson.runningCount)/$($serviceJson.desiredCount) tasks (Attempt $attempts/$maxAttempts)" -NoNewline
        Start-Sleep -Seconds 10
    }
}

Write-Host ""  # New line after the progress indicator

if ($stable) {
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
    
    # Display the latest deployment - prevent paging with specific query
    $tempServiceFile = [System.IO.Path]::GetTempFileName()
    
    aws ecs describe-services --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --services $ServiceName --query "services[0].{serviceName:serviceName,status:status,desiredCount:desiredCount,runningCount:runningCount,pendingCount:pendingCount}" --output json | Out-File -FilePath $tempServiceFile
    $serviceJson = Get-Content -Path $tempServiceFile -Raw | ConvertFrom-Json
    Remove-Item -Path $tempServiceFile -Force
    
    Write-Host "`nService Status:" -ForegroundColor Green
    Write-Host "Service Name: $($serviceJson.serviceName)"
    Write-Host "Status: $($serviceJson.status)"
    Write-Host "Desired Count: $($serviceJson.desiredCount)"
    Write-Host "Running Count: $($serviceJson.runningCount)"
    Write-Host "Pending Count: $($serviceJson.pendingCount)"
    
    # Get the running tasks - prevent paging
    $tasksJson = aws ecs list-tasks --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --service-name $ServiceName --output json | ConvertFrom-Json
    
    if ($tasksJson.taskArns.Count -gt 0) {
        Write-Host "`nRunning Tasks:" -ForegroundColor Green
        foreach ($taskArn in $tasksJson.taskArns) {
            Write-Host "- $taskArn"
        }
    }
    else {
        Write-Host "`nNo running tasks found." -ForegroundColor Yellow
    }
    
    # Display load balancer DNS
    Write-Host "`nApplication is accessible at:" -ForegroundColor Green
    Write-Host "http://agentic-deals-alb-1007520943.us-east-1.elb.amazonaws.com"
    
    Write-Host "`nTo check logs, use:" -ForegroundColor Cyan
    Write-Host "aws logs get-log-events --profile $ProfileName --region $Region --log-group-name /ecs/agentic-deals-container --log-stream-name STREAM_NAME --no-cli-pager"
    
    Write-Host "`nTo get the log stream name for a task, use:" -ForegroundColor Cyan
    Write-Host "aws ecs describe-tasks --profile $ProfileName --region $Region --cluster $ClusterName --tasks TASK_ID --query 'tasks[0].containers[0].name' --no-cli-pager"
}
else {
    Write-Host "Deployment did not stabilize within the expected time." -ForegroundColor Yellow
    Write-Host "Please check the AWS ECS console for more details." -ForegroundColor Yellow
    
    # Display the current deployments - prevent paging and use temp file
    $tempEventsFile = [System.IO.Path]::GetTempFileName()
    
    aws ecs describe-services --no-cli-pager --profile $ProfileName --region $Region --cluster $ClusterName --services $ServiceName --query "services[0].{serviceName:serviceName,status:status,desiredCount:desiredCount,runningCount:runningCount,pendingCount:pendingCount,events:events[0:3]}" --output json | Out-File -FilePath $tempEventsFile
    $serviceJson = Get-Content -Path $tempEventsFile -Raw | ConvertFrom-Json
    Remove-Item -Path $tempEventsFile -Force
    
    Write-Host "`nService Status:" -ForegroundColor Yellow
    Write-Host "Service Name: $($serviceJson.serviceName)"
    Write-Host "Status: $($serviceJson.status)"
    Write-Host "Desired Count: $($serviceJson.desiredCount)"
    Write-Host "Running Count: $($serviceJson.runningCount)"
    Write-Host "Pending Count: $($serviceJson.pendingCount)"
    
    Write-Host "`nRecent Events:" -ForegroundColor Yellow
    foreach ($event in $serviceJson.events) {
        Write-Host "- $($event.message)"
    }
}

Write-StepHeader "Deployment Process Completed" 