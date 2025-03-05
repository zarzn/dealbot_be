# Deployment Scripts

This directory contains scripts for deploying and running the application in various environments.

## Scripts

- `start.sh`: Script to start the application in development mode
- `entrypoint.prod.sh`: Production entrypoint script for Docker containers
- `aws_ecs_deploy.ps1`: PowerShell script for deploying to AWS ECS
- `aws_migrate.py`: Python script for database migrations in AWS
- `DB_MIGRATION_README.md`: Documentation for database migration process

## Usage

### Start Application (Development)

```bash
./backend/scripts/deployment/start.sh
```

### Production Entrypoint

This script is used as the entrypoint in the Docker container for production deployment:

```dockerfile
ENTRYPOINT ["/app/scripts/deployment/entrypoint.prod.sh"]
```

The entrypoint script now automatically:
- Checks for database connectivity
- Creates the database if it doesn't exist
- Runs all pending migrations
- Creates initial data if needed

For more details on the database migration process, see [DB_MIGRATION_README.md](./DB_MIGRATION_README.md).

### AWS ECS Deployment

The `aws_ecs_deploy.ps1` script automates the deployment process to AWS ECS:

```powershell
# Navigate to the backend directory
cd backend

# Run the deployment script
./scripts/deployment/aws_ecs_deploy.ps1 -ProfileName "agentic-deals-deployment" -Region "us-east-1"
```

#### Script Parameters

- `-ProfileName`: AWS CLI profile name (default: "agentic-deals-deployment")
- `-Region`: AWS region (default: "us-east-1")
- `-ImageTag`: Docker image tag (default: "latest")
- `-ClusterName`: ECS cluster name (default: "agentic-deals-cluster")
- `-ServiceName`: ECS service name (default: "agentic-deals-service")
- `-TaskDefFile`: Path to the task definition JSON file (default: "./agentic-deals-task-def.json")

## Docker Deployment

The `Dockerfile.prod` in the root directory is used for building the production image:

```powershell
# Build the production image
docker build -t agentic-deals-backend:latest -f Dockerfile.prod .
```

## AWS Deployment Process

1. **Build and Tag Docker Image**:
   ```powershell
   docker build -t agentic-deals-backend:latest -f Dockerfile.prod .
   docker tag agentic-deals-backend:latest 586794462529.dkr.ecr.us-east-1.amazonaws.com/agentic-deals-repository:latest
   ```

2. **Push to ECR**:
   ```powershell
   aws ecr get-login-password --profile agentic-deals-deployment --region us-east-1 | docker login --username AWS --password-stdin 586794462529.dkr.ecr.us-east-1.amazonaws.com
   docker push 586794462529.dkr.ecr.us-east-1.amazonaws.com/agentic-deals-repository:latest
   ```

3. **Update Task Definition**:
   ```powershell
   aws ecs register-task-definition --profile agentic-deals-deployment --region us-east-1 --cli-input-json file://agentic-deals-task-def-new.json
   ```

4. **Update ECS Service**:
   ```powershell
   aws ecs update-service --profile agentic-deals-deployment --cluster agentic-deals-cluster --service agentic-deals-service --force-new-deployment --region us-east-1
   ```

5. **Monitor Deployment**:
   ```powershell
   aws ecs describe-services --profile agentic-deals-deployment --cluster agentic-deals-cluster --services agentic-deals-service --region us-east-1
   ```

## Database Migrations

The application now handles database creation and migrations automatically during startup. No separate tasks or manual steps are required.

If you still need to run migrations separately (for example, during a database-only update), you can use the ECS migration task:

```powershell
# Register the migration task definition
aws ecs register-task-definition --profile agentic-deals-deployment --region us-east-1 --cli-input-json file://hardcoded-migration-task-definition.json

# Run the migration task
aws ecs run-task --profile agentic-deals-deployment --region us-east-1 --cluster agentic-deals-cluster --task-definition agentic-deals-migrations:latest --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[subnet-ids],securityGroups=[sg-ids],assignPublicIp=DISABLED}"
```

## Notes

- The `start.sh` script is for development purposes
- The `entrypoint.prod.sh` script is used in production Docker containers
- Make sure the scripts have executable permissions before using them:
  ```bash
  chmod +x backend/scripts/deployment/*.sh
  ```
- For AWS deployment, use the PowerShell scripts from a Windows environment
- Refer to the full documentation in the `docs` directory for detailed deployment guides 