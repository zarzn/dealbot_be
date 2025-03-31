# Deployment Instructions

These instructions guide you through the process of building and deploying the updated Docker image with the fixed database initialization process.

## 1. Set up Parameter Store

Ensure the RESET_DB parameter is set in AWS Parameter Store:

```powershell
# Set RESET_DB to true to reset the database on next deployment
aws ssm put-parameter --name '/agentic-deals/RESET_DB' --value 'true' --type String --overwrite --profile agentic-deals-deployment --region us-east-1
```

## 2. Build the Docker Image

Navigate to the backend directory and build the Docker image:

```powershell
cd C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend
docker build -t agentic-deals-backend:latest .
```

## 3. Tag and Push the Docker Image

Tag the image and push it to Amazon ECR:

```powershell
# Log in to Amazon ECR
aws ecr get-login-password --region us-east-1 --profile agentic-deals-deployment | docker login --username AWS --password-stdin 586794462529.dkr.ecr.us-east-1.amazonaws.com

# Tag the image
docker tag agentic-deals-backend:latest 586794462529.dkr.ecr.us-east-1.amazonaws.com/agentic-deals-backend:latest

# Push the image
docker push 586794462529.dkr.ecr.us-east-1.amazonaws.com/agentic-deals-backend:latest
```

## 4. Deploy to ECS

There are two ways to deploy the new image to ECS:

### Option 1: Automated Deployment Script

Use the provided deployment script:

```powershell
cd C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend\scripts\deployment
.\aws_ecs_deploy.ps1 -ForceNewDeployment -SkipBuild -SkipPush
```

### Option 2: Manual Deployment

Force a new deployment through the AWS CLI:

```powershell
aws ecs update-service --cluster agentic-deals-cluster --service agentic-deals-service --force-new-deployment --profile agentic-deals-deployment --region us-east-1
```

## 5. Monitor the Deployment

Monitor the deployment progress and check the logs:

```powershell
# Check the service status
aws ecs describe-services --cluster agentic-deals-cluster --services agentic-deals-service --profile agentic-deals-deployment --region us-east-1 --no-cli-pager

# Get task ARNs
aws ecs list-tasks --cluster agentic-deals-cluster --profile agentic-deals-deployment --region us-east-1 --no-cli-pager

# Check task details (replace TASK_ARN with the actual task ARN)
aws ecs describe-tasks --cluster agentic-deals-cluster --tasks TASK_ARN --profile agentic-deals-deployment --region us-east-1 --no-cli-pager

# Check the logs (replace LOG_STREAM with the actual log stream)
aws logs get-log-events --log-group-name "/ecs/agentic-deals-container" --log-stream-name LOG_STREAM --profile agentic-deals-deployment --region us-east-1 --no-cli-pager
```

## 6. Reset RESET_DB Parameter (After Successful Deployment)

After confirming the database has been reset successfully, set RESET_DB back to false:

```powershell
aws ssm put-parameter --name '/agentic-deals/RESET_DB' --value 'false' --type String --overwrite --profile agentic-deals-deployment --region us-east-1
```

## 7. Verify the Application

Access the application to verify it's working correctly:

1. Check the API Gateway to ensure the API is accessible
2. Verify the health check endpoint is returning a 200 OK response
3. Test core functionality to ensure the application is working as expected

## Troubleshooting

### Health Check Issues

If health checks are failing, check the ECS service events and CloudWatch logs:

```powershell
# Check target health
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:us-east-1:586794462529:targetgroup/agentic-deals-tg/38e7f513f1afde57 --profile agentic-deals-deployment --region us-east-1 --no-cli-pager

# View recent logs
aws logs get-log-events --log-group-name "/ecs/agentic-deals-container" --log-stream-name "ecs/agentic-deals-app/LATEST_TASK_ID" --profile agentic-deals-deployment --region us-east-1 --no-cli-pager --limit 100
```

### Database Reset Issues

If the database reset is not working, verify:

1. The RESET_DB parameter is correctly set to "true" in Parameter Store
2. The entrypoint script is being executed correctly (check logs)
3. The create_db.py script is functioning properly (check logs for any errors)

### Container Startup Issues

If the container fails to start:

1. Check the CPU and memory allocation in the task definition
2. Verify the environment variables and secrets are correctly configured
3. Check for any errors in the container logs 