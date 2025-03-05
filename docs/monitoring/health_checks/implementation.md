# Health Check Implementation Guide

This document provides detailed information about the health check implementation in the AI Agentic Deals System, including the available endpoints, configuration, and best practices for AWS deployment.

## Available Health Check Endpoints

The application provides multiple health check endpoints to accommodate different use cases:

### 1. Root Health Check (`/health`)

This is the main health check endpoint designed specifically for container health monitoring and load balancer health checks.

**Endpoint**: `/health`  
**Method**: GET  
**Required Permissions**: None (publicly accessible)

**Response Example**:
```json
{
  "status": "healthy"
}
```

### 2. Additional Health Check Endpoints

For compatibility with various load balancer configurations, the following alternative endpoints are also available:

- **Endpoint**: `/healthcheck`  
- **Endpoint**: `/api/healthcheck`  

These endpoints have the same behavior as the root `/health` endpoint and are designed for container health monitoring.

### 3. API Health Check (`/api/v1/health`)

This endpoint performs a more comprehensive health check including database and Redis connection validation.

**Endpoint**: `/api/v1/health`  
**Method**: GET  
**Required Permissions**: None (publicly accessible)

**Response Example**:
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "uptime_seconds": 3600,
  "host": "hostname",
  "ip": "127.0.0.1",
  "aws_environment": true
}
```

### 4. Service-Specific Health Checks

Individual service health checks are available for more granular monitoring:

- **Database**: `/api/v1/health/database`
- **Redis**: `/api/v1/health/redis`

## Configuration

Health checks can be configured using environment variables:

```env
# Enable/disable health check (default: true)
HEALTH_CHECK_ENABLED=true

# Configure deep health check (may impact performance)
HEALTH_CHECK_DEEP_ENABLED=true

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL=60

# Health check timeout (seconds)
HEALTH_CHECK_TIMEOUT=5

# Services to check in deep health check
HEALTH_CHECK_SERVICES="database,redis,external"
```

## AWS Integration

### ECS Health Checks

Our application's ECS task definition is configured with a health check that targets the `/health` endpoint:

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

### Application Load Balancer (ALB) Health Checks

For ALB health check configuration:

1. Target Group Configuration:
   - Health check path: `/health`
   - Health check protocol: HTTP
   - Health check port: traffic port
   - Healthy threshold: 3
   - Unhealthy threshold: 2
   - Timeout: 5 seconds
   - Interval: 30 seconds
   - Success codes: 200

### CloudWatch Alarms

Set up CloudWatch alarms to monitor the health check status:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name aideals-health-check-alarm \
  --alarm-description "Alarm for AI Agentic Deals System health check" \
  --metric-name HealthyHostCount \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=TargetGroup,Value=<target-group-arn> Name=LoadBalancer,Value=<load-balancer-arn> \
  --evaluation-periods 2 \
  --alarm-actions <sns-topic-arn>
```

## Implementation Details

The health check system is implemented in multiple locations:

1. **Container/Load Balancer Health Checks**: Located in `backend/app.py`
   ```python
   @app.get("/health")
   @app.get("/healthcheck")
   @app.get("/api/healthcheck")
   async def health_check():
       """Basic health check endpoint for container health monitoring.
       
       This endpoint always returns healthy and doesn't check any dependencies.
       It's designed specifically for AWS ECS health checks.
       """
       logger.info("Health check endpoint hit")
       return JSONResponse(content={"status": "healthy"})
   ```

2. **API Health Checks**: Located in `backend/core/api/v1/health/router.py`
   ```python
   @router.get("")
   async def health_check(
       response: Response,
       db: AsyncSession = Depends(get_db)
   ):
       """Health check endpoint that validates database and Redis connections."""
       # Implementation checks database and Redis connections
       # ...
   ```

## Best Practices

1. **Health Check Simplicity**:
   - The primary load balancer health check (`/health`) should be lightweight and always return a 200 status
   - More comprehensive health checks should be used for monitoring but not for container health decisions

2. **Multiple Health Check Endpoints**:
   - Maintain multiple compatible health check endpoints (`/health`, `/healthcheck`, `/api/healthcheck`)
   - This ensures compatibility with various load balancer configurations

3. **Deployment Considerations**:
   - Always test health checks before deployment
   - Remember that health checks are critical for proper service discovery
   - Set an appropriate startup period to allow the application time to initialize

4. **Monitoring**:
   - Set up CloudWatch alarms for health check failures
   - Monitor the API health endpoint (`/api/v1/health`) for detailed system health
   - Log health check results for troubleshooting

## Troubleshooting

### Common Issues

1. **ECS Health Check Failures**:
   - Verify the container is exposing the correct port
   - Check that the health check path is correct in the task definition
   - Ensure the application responds to the health check endpoint
   - Check application logs for startup errors

2. **ALB Health Check Failures**:
   - Verify target group health check configuration
   - Check security groups allow health check traffic
   - Inspect application logs for health check requests
   - Verify health check response is a valid HTTP 200

### Recovery Actions

When health checks fail:

1. Check application logs for errors
2. Verify network connectivity
3. Ensure the application is running and responsive
4. Check for configuration issues in the health check setup 