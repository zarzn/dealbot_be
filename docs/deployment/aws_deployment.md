# AWS Deployment Guide for AI Agentic Deals System

This comprehensive guide provides detailed instructions for deploying the AI Agentic Deals System (both backend and frontend) on AWS infrastructure.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [AWS Infrastructure Overview](#aws-infrastructure-overview)
3. [Environment Configuration](#environment-configuration)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Monitoring and Logging](#monitoring-and-logging)
7. [Security Best Practices](#security-best-practices)
8. [Maintenance and Updates](#maintenance-and-updates)
9. [Troubleshooting](#troubleshooting)
10. [Cost Optimization](#cost-optimization)

## Prerequisites

Before deploying to AWS, ensure you have:

- AWS account with administrative access
- AWS CLI installed and configured with the appropriate profile
- Docker installed for building container images
- Git repository access for the codebase
- Appropriate IAM permissions for required services
- Domain name (if using custom domain for frontend)
- API keys for external services (DeepSeek, OpenAI, etc.)

## AWS Infrastructure Overview

### Required AWS Services

#### Shared Infrastructure
- **Identity and Access Management (IAM)**
  - User management and permissions
  - Service roles for ECS, Lambda, etc.

- **Virtual Private Cloud (VPC)**
  - Private and public subnets
  - Security groups and NACLs
  - Internet and NAT gateways

#### Backend Infrastructure
- **Elastic Container Registry (ECR)**
  - Stores Docker images
  
- **Elastic Container Service (ECS)**
  - Runs containerized backend
  - Fargate for serverless container execution
  
- **Application Load Balancer (ALB)**
  - HTTP/HTTPS routing
  - Health checks
  
- **RDS (PostgreSQL)**
  - Main database
  - Multi-AZ for production
  
- **ElastiCache (Redis)**
  - Session management
  - Caching layer
  
- **Secrets Manager**
  - API keys
  - Database credentials
  
- **Parameter Store**
  - Configuration parameters
  
- **API Gateway**
  - REST API endpoints
  - WebSocket API (for real-time features)

#### Frontend Infrastructure
- **S3**
  - Static website hosting
  
- **CloudFront**
  - CDN for content delivery
  - HTTPS termination
  
- **Certificate Manager (ACM)**
  - SSL/TLS certificates
  
- **Route 53**
  - DNS management (if using custom domain)

## Environment Configuration

### Environment Variables

The application uses environment variables for configuration. In AWS, these can be provided through:

1. ECS Task Definition Environment Variables
2. AWS Parameter Store
3. AWS Secrets Manager

### AWS Parameter Store

Parameters should be stored with the following path structure:

```
/aideals/{environment}/{parameter_name}
```

For example:
- `/aideals/production/DATABASE_URL`
- `/aideals/staging/REDIS_URL`

### AWS Secrets Manager

Sensitive configuration (passwords, API keys) should be stored in AWS Secrets Manager with the following naming pattern:

```
aideals/{environment}/secrets
```

For example:
- `aideals/production/secrets`
- `aideals/staging/secrets`

Recommended secrets to store:
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`

### Environment-Specific Configurations

Create environment-specific configuration files:

1. Backend: `.env.production`
2. Frontend: `.env.production`

Example backend `.env.production`:
```env
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY="your-secret-key"

# Database Configuration
POSTGRES_USER="aideals_user"
POSTGRES_PASSWORD="from-secrets-manager"
POSTGRES_DB="aideals_production"
POSTGRES_HOST="your-rds-instance.region.rds.amazonaws.com"
POSTGRES_PORT="5432"

# Redis Configuration
REDIS_HOST="your-elasticache.region.cache.amazonaws.com"
REDIS_PORT="6379"
REDIS_DB="0"
REDIS_PASSWORD="from-secrets-manager"
REDIS_SSL="true"

# API keys (retrieved from Secrets Manager)
DEEPSEEK_API_KEY="from-secrets-manager"
OPENAI_API_KEY="from-secrets-manager"
```

## Backend Deployment

### Containerization

1. Update the `Dockerfile.prod` for production optimizations:
   ```dockerfile
   FROM python:3.10-slim
   
   WORKDIR /app
   
   # Install dependencies
   COPY backend/requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Copy application code
   COPY backend/ .
   
   # Set environment variables
   ENV PYTHONPATH=/app
   ENV ENVIRONMENT=production
   
   # Expose port
   EXPOSE 8000
   
   # Run the application
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. Build and tag the Docker image:
   ```bash
   docker build -f Dockerfile.prod -t aideals-backend:latest .
   ```

3. Test the container locally:
   ```bash
   docker run -p 8000:8000 --env-file .env.production aideals-backend:latest
   ```

### AWS ECR Setup

1. Create a repository:
   ```bash
   aws ecr create-repository --repository-name aideals-backend
   ```

2. Authenticate Docker to ECR:
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<region>.amazonaws.com
   ```

3. Tag and push the image:
   ```bash
   docker tag aideals-backend:latest <your-aws-account-id>.dkr.ecr.<region>.amazonaws.com/aideals-backend:latest
   docker push <your-aws-account-id>.dkr.ecr.<region>.amazonaws.com/aideals-backend:latest
   ```

### ECS Cluster and Task Definition

1. Create an ECS cluster:
   ```bash
   aws ecs create-cluster --cluster-name aideals-cluster
   ```

2. Create a task definition:
   ```json
   {
     "family": "aideals-backend",
     "networkMode": "awsvpc",
     "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
     "taskRoleArn": "arn:aws:iam::<account-id>:role/aidealsTaskRole",
     "containerDefinitions": [
       {
         "name": "aideals-backend",
         "image": "<your-aws-account-id>.dkr.ecr.<region>.amazonaws.com/aideals-backend:latest",
         "essential": true,
         "portMappings": [
           {
             "containerPort": 8000,
             "hostPort": 8000,
             "protocol": "tcp"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/aideals-backend",
             "awslogs-region": "<region>",
             "awslogs-stream-prefix": "ecs"
           }
         },
         "healthCheck": {
           "command": [
             "CMD-SHELL",
             "curl -f http://localhost:8000/health || exit 1"
           ],
           "interval": 30,
           "timeout": 10,
           "retries": 3,
           "startPeriod": 120
         }
       }
     ],
     "requiresCompatibilities": [
       "FARGATE"
     ],
     "cpu": "512",
     "memory": "1024"
   }
   ```

### Health Check Configuration

Our application provides multiple health check endpoints to ensure compatibility with various load balancer configurations:

1. **Primary Health Check Endpoint**:
   - `/health` - This is the main health check endpoint used by ECS and ALB.
   - Always returns a 200 status code with `{"status": "healthy"}` payload.
   - Implemented directly in `app.py` for reliability.

2. **Alternative Health Check Endpoints**:
   - `/healthcheck` and `/api/healthcheck` - These are additional endpoints that behave identically to `/health`.
   - Provided for compatibility with different load balancer path expectations.

3. **Health Check Implementation**:
   ```python
   # In backend/app.py
   @app.get("/health")
   @app.get("/healthcheck")
   @app.get("/api/healthcheck")
   async def health_check():
       """Basic health check endpoint for container health monitoring."""
       logger.info("Health check endpoint hit")
       return JSONResponse(content={"status": "healthy"})
   ```

4. **Task Definition Configuration**:
   The ECS task definition should use the `/health` endpoint for container health checks:
   ```json
   "healthCheck": {
     "command": [
       "CMD-SHELL",
       "curl -f http://localhost:8000/health || exit 1"
     ],
     "interval": 30,
     "timeout": 10,
     "retries": 3,
     "startPeriod": 120
   }
   ```

5. **ALB Target Group Configuration**:
   - Health check path: `/health`
   - Health check protocol: HTTP
   - Health check port: traffic port
   - Healthy threshold: 3
   - Unhealthy threshold: 2
   - Timeout: 5 seconds
   - Interval: 30 seconds
   - Success codes: 200

### Troubleshooting Health Checks

If services are failing health checks:

1. **Verify Container Startup**:
   - Check that the container is starting properly.
   - Review container logs for startup errors.
   - Ensure the application is binding to the correct port (8000).

2. **Test Health Endpoint Locally**:
   ```bash
   # Test from outside the container
   curl http://localhost:8000/health
   
   # Test from inside the container
   docker exec <container-id> curl http://localhost:8000/health
   ```

3. **Check Network Configuration**:
   - Verify security groups allow traffic to the health check port.
   - Ensure load balancer can reach the containers.
   - Check that the health check path is correct in both ECS task definition and ALB target group.

4. **Review Application Logs**:
   - Look for health check requests in the application logs.
   - Check for any errors occurring during health check requests.
   - Verify the application is responding with HTTP 200 status codes.

### ECS Service Creation

1. Create a security group:
   ```bash
   aws ec2 create-security-group --group-name aideals-backend-sg \
     --description "Security group for AI Agentic Deals backend" \
     --vpc-id <vpc-id>
   ```

2. Allow inbound traffic:
   ```bash
   aws ec2 authorize-security-group-ingress --group-id <sg-id> \
     --protocol tcp --port 8000 --cidr 0.0.0.0/0
   ```

3. Create the ECS service:
   ```bash
   aws ecs create-service \
     --cluster aideals-cluster \
     --service-name aideals-backend-service \
     --task-definition aideals-backend:1 \
     --desired-count 2 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<subnet-1>,<subnet-2>],securityGroups=[<sg-id>],assignPublicIp=ENABLED}" \
     --load-balancers "targetGroupArn=<target-group-arn>,containerName=aideals-backend,containerPort=8000"
   ```

### API Gateway Configuration

1. Create a REST API:
   ```bash
   aws apigateway create-rest-api --name "AI Agentic Deals API" --description "API for AI Agentic Deals System"
   ```

2. Configure routes to the ECS backend service

3. Create a deployment:
   ```bash
   aws apigateway create-deployment --rest-api-id <api-id> --stage-name prod
   ```

### WebSocket API (if needed)

1. Create a WebSocket API:
   ```bash
   aws apigatewayv2 create-api --name "AI Agentic Deals WebSocket" --protocol-type WEBSOCKET --route-selection-expression "\$request.body.action"
   ```

2. Configure routes ($connect, $disconnect, and custom routes)

3. Deploy the WebSocket API:
   ```bash
   aws apigatewayv2 create-deployment --api-id <api-id> --stage-name prod
   ```

## Frontend Deployment

### Building the Frontend

1. Configure the production environment variables in `.env.production`:
   ```
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   NEXT_PUBLIC_WS_URL=wss://ws.yourdomain.com
   ```

2. Build the frontend:
   ```bash
   cd frontend
   npm ci
   npm run build
   ```

### S3 Bucket Setup

1. Create an S3 bucket:
   ```bash
   aws s3 mb s3://aideals-frontend
   ```

2. Configure the bucket for static website hosting:
   ```bash
   aws s3 website s3://aideals-frontend --index-document index.html --error-document index.html
   ```

3. Upload the build files:
   ```bash
   aws s3 sync ./frontend/build/ s3://aideals-frontend --delete
   ```

### CloudFront Configuration

1. Create an SSL certificate in ACM:
   ```bash
   aws acm request-certificate --domain-name yourdomain.com --validation-method DNS --subject-alternative-names www.yourdomain.com
   ```

2. Create a CloudFront distribution:
   ```bash
   aws cloudfront create-distribution \
     --origin-domain-name aideals-frontend.s3.amazonaws.com \
     --default-root-object index.html \
     --aliases yourdomain.com www.yourdomain.com \
     --viewer-certificate "ACMCertificateArn=<certificate-arn>,SSLSupportMethod=sni-only" \
     --default-cache-behavior "TargetOriginId=S3-aideals-frontend,ViewerProtocolPolicy=redirect-to-https,AllowedMethods=GET,HEAD,OPTIONS,CachePolicyId=<cache-policy-id>"
   ```

3. Configure error page routing for SPA:
   ```bash
   aws cloudfront update-distribution --id <distribution-id> --default-root-object index.html \
     --custom-error-responses "Quantity=1,Items=[{ErrorCode=404,ResponseCode=200,ResponsePagePath=/index.html}]"
   ```

### DNS Configuration (Route 53)

1. Create a hosted zone (if not existing):
   ```bash
   aws route53 create-hosted-zone --name yourdomain.com --caller-reference $(date +%s)
   ```

2. Create record sets:
   ```bash
   aws route53 change-resource-record-sets --hosted-zone-id <zone-id> \
     --change-batch '{"Changes":[{"Action":"CREATE","ResourceRecordSet":{"Name":"yourdomain.com","Type":"A","AliasTarget":{"HostedZoneId":"Z2FDTNDATAQYW2","DNSName":"<cloudfront-domain>","EvaluateTargetHealth":false}}}]}'
   ```

## Monitoring and Logging

### CloudWatch Logs and Metrics

1. Create log groups:
   ```bash
   aws logs create-log-group --log-group-name /ecs/aideals-backend
   aws logs create-log-group --log-group-name /api-gateway/aideals
   ```

2. Create CloudWatch alarms:
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name aideals-backend-cpu-high \
     --alarm-description "CPU utilization high" \
     --metric-name CPUUtilization \
     --namespace AWS/ECS \
     --statistic Average \
     --period 60 \
     --threshold 80 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=ClusterName,Value=aideals-cluster Name=ServiceName,Value=aideals-backend-service \
     --evaluation-periods 2 \
     --alarm-actions <sns-topic-arn>
   ```

### Health Checks

Configure health checks at multiple levels:

1. Application level: `/health` endpoint
2. ECS health check in task definition
3. ALB health check for service
4. CloudWatch alarms for service metrics

## Security Best Practices

1. Use IAM roles with least privilege principle
2. Store sensitive information in Secrets Manager
3. Enable VPC flow logs for network monitoring
4. Configure security groups to restrict traffic
5. Use AWS WAF for web application firewall protection
6. Enable CloudTrail for API activity monitoring
7. Enable GuardDuty for threat detection
8. Encrypt data at rest and in transit
9. Implement CORS policies for API Gateway
10. Configure SSL/TLS for all communications

## Maintenance and Updates

### Database Backups

1. Configure RDS automated backups:
   ```bash
   aws rds modify-db-instance \
     --db-instance-identifier aideals-db \
     --backup-retention-period 7 \
     --preferred-backup-window "03:00-05:00" \
     --apply-immediately
   ```

### Deployment Pipeline

1. Create a CI/CD pipeline using GitHub Actions or AWS CodePipeline
2. Implement rolling deployments for zero-downtime updates
3. Configure automated testing before deployment
4. Set up automated rollback on failure

### Monitoring and Alerting

1. Set up SNS topics and subscriptions for alerts
2. Configure CloudWatch dashboards for system monitoring
3. Implement alerting for key metrics:
   - Service health
   - Error rates
   - API latency
   - Database performance
   - Cost anomalies

## Troubleshooting

### Common Issues and Solutions

1. **ECS Service Deployment Failures**
   - Check task definition validity
   - Verify IAM roles and permissions
   - Check container logs in CloudWatch

2. **Database Connection Issues**
   - Verify security group rules
   - Check database credentials
   - Test connectivity from a bastion host

3. **API Gateway Errors**
   - Verify API Gateway configuration
   - Check integrations with backend
   - Review CloudWatch logs for API Gateway

### Debug Tools

1. Use AWS CloudShell for quick CLI access
2. Deploy a bastion host for secure database access
3. Use CloudWatch Logs Insights for log analysis

## Cost Optimization

### Strategies

1. **Right-sizing resources**
   - Use AWS Compute Optimizer for recommendations
   - Adjust ECS task CPU and memory

2. **Auto Scaling**
   - Implement ECS auto scaling for varying loads
   - Set min/max capacity based on usage patterns

3. **Reserved Instances/Savings Plans**
   - Consider Reserved Instances for RDS
   - Evaluate Compute Savings Plans for ECS

4. **S3 Storage Classes**
   - Use Intelligent-Tiering for log storage
   - Implement lifecycle policies

### Cost Monitoring

1. Set up AWS Budgets for cost tracking
2. Configure Cost Anomaly Detection
3. Use Cost Explorer to identify optimization opportunities

## Conclusion

This guide provides a comprehensive approach to deploying the AI Agentic Deals System on AWS. By following these instructions, you'll create a secure, scalable, and cost-effective infrastructure that meets production requirements.

For specific details on individual components, refer to the other documents in the deployment directory. 