# Health Checks Implementation

## Overview

This document outlines the implementation of health check endpoints across the AI Agentic Deals System. Health checks are critical components that allow monitoring systems to verify the operational status of services, dependencies, and the overall system health, enabling automated detection of issues and proactive resolution.

## Health Check Types

The system implements several types of health checks to provide comprehensive monitoring:

### 1. Liveness Checks

Liveness checks determine if a service is running and responsive. These are basic checks that verify if the application process is alive and can respond to HTTP requests.

**Purpose:**
- Detect crashed or deadlocked services
- Allow orchestration systems (e.g., Kubernetes) to restart unresponsive instances
- Provide quick verification of basic service availability

**Implementation Characteristics:**
- Lightweight and fast execution (< 50ms)
- No external dependency checks
- No business logic validation

### 2. Readiness Checks

Readiness checks determine if a service is ready to handle requests. These checks verify that the service and its dependencies are available and properly configured.

**Purpose:**
- Confirm service can process incoming requests
- Prevent routing traffic to partially initialized services
- Verify required external dependencies are accessible

**Implementation Characteristics:**
- Verify database connections
- Check critical service dependencies
- Validate configuration settings
- Test cache availability

### 3. Deep Health Checks

Deep health checks perform comprehensive verification of system components and business functionality.

**Purpose:**
- Detailed diagnostic information for operations teams
- Verification of business logic functionality
- Early detection of degraded performance
- Comprehensive dependency status

**Implementation Characteristics:**
- Probing of all critical dependencies
- Performance timing information
- Component-level status reporting
- Resource utilization metrics

## Endpoint Design

### Standard Endpoints

The system implements the following standardized health check endpoints:

| Endpoint | Type | Authentication | Description |
|----------|------|----------------|-------------|
| `/health/live` | Liveness | None | Basic liveness verification |
| `/health/ready` | Readiness | None | Service readiness status |
| `/health` | Deep | API Key | Comprehensive health status |
| `/health/dependency/{name}` | Specific | API Key | Status of specific dependency |

### Response Format

All health check endpoints return responses in a standardized JSON format:

```json
{
  "status": "pass|warn|fail",
  "version": "1.2.3",
  "description": "AI Agentic Deals API Service",
  "checks": [
    {
      "name": "database",
      "status": "pass",
      "time": "2023-06-01T12:34:56Z",
      "duration_ms": 15,
      "output": "Connected successfully"
    },
    {
      "name": "redis",
      "status": "warn",
      "time": "2023-06-01T12:34:56Z",
      "duration_ms": 120,
      "output": "High latency detected"
    }
  ]
}
```

The response follows these guidelines:
- `status`: Overall status (pass, warn, fail)
- `version`: Application version
- `checks`: Array of individual component checks
- Each check includes name, status, timestamp, duration, and optional output

### Status Codes

Health check endpoints use HTTP status codes to indicate health:

| Status | HTTP Code | Description |
|--------|-----------|-------------|
| pass | 200 | Service is healthy |
| warn | 200 | Service is degraded but functional |
| fail | 503 | Service is not operational |

## Implementation Details

### FastAPI Implementation

The health check endpoints are implemented using FastAPI's dependency injection system:

```python
# health_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List, Optional
import time
from datetime import datetime

from core.services.health import HealthService
from core.dependencies import get_health_service
from core.models.health import HealthResponse, HealthCheck, HealthStatus

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/live", response_model=HealthResponse)
async def liveness_check():
    """
    Basic liveness check to verify service is running.
    This endpoint should be fast and not depend on external services.
    """
    return HealthResponse(
        status=HealthStatus.PASS,
        version=settings.VERSION,
        description="AI Agentic Deals API Service",
        checks=[
            HealthCheck(
                name="api_service",
                status=HealthStatus.PASS,
                time=datetime.utcnow().isoformat(),
                duration_ms=0,
                output="Service is alive"
            )
        ]
    )

@router.get("/ready", response_model=HealthResponse)
async def readiness_check(health_service: HealthService = Depends(get_health_service)):
    """
    Readiness check to verify service can handle requests.
    Checks critical dependencies like database and cache.
    """
    start_time = time.time()
    checks: List[HealthCheck] = []
    overall_status = HealthStatus.PASS
    
    # Check database
    db_check = await health_service.check_database()
    checks.append(db_check)
    if db_check.status == HealthStatus.FAIL:
        overall_status = HealthStatus.FAIL
    elif db_check.status == HealthStatus.WARN and overall_status != HealthStatus.FAIL:
        overall_status = HealthStatus.WARN
    
    # Check Redis
    redis_check = await health_service.check_redis()
    checks.append(redis_check)
    if redis_check.status == HealthStatus.FAIL:
        overall_status = HealthStatus.FAIL
    elif redis_check.status == HealthStatus.WARN and overall_status != HealthStatus.FAIL:
        overall_status = HealthStatus.WARN
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    response = HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        description="AI Agentic Deals API Service",
        checks=checks
    )
    
    if overall_status == HealthStatus.FAIL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    
    return response

@router.get("", response_model=HealthResponse)
async def deep_health_check(
    health_service: HealthService = Depends(get_health_service),
    api_key: str = Depends(verify_api_key)
):
    """
    Comprehensive health check with detailed diagnostic information.
    Requires API key authentication.
    """
    start_time = time.time()
    checks: List[HealthCheck] = []
    overall_status = HealthStatus.PASS
    
    # Run all component checks
    component_checks = await health_service.check_all_components()
    checks.extend(component_checks)
    
    # Determine overall status
    for check in component_checks:
        if check.status == HealthStatus.FAIL:
            overall_status = HealthStatus.FAIL
            break
        elif check.status == HealthStatus.WARN and overall_status != HealthStatus.FAIL:
            overall_status = HealthStatus.WARN
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    response = HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        description="AI Agentic Deals API Service",
        checks=checks
    )
    
    if overall_status == HealthStatus.FAIL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    
    return response
```

### Health Service Implementation

The Health Service encapsulates the logic for checking different components:

```python
# health_service.py
from typing import List, Dict, Any
from datetime import datetime
import time
import asyncio

from core.models.health import HealthCheck, HealthStatus
from core.database import get_db
from core.services.redis import get_redis_service
from core.services.llm import get_llm_service

class HealthService:
    """Service for checking the health of various system components."""
    
    async def check_database(self) -> HealthCheck:
        """
        Check database connection and basic query functionality.
        """
        start_time = time.time()
        try:
            db = await anext(get_db())
            # Execute simple query to verify connection
            result = await db.execute("SELECT 1")
            await result.fetchone()
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.PASS
            output = "Database connection successful"
            
            # If query took too long, mark as warning
            if duration_ms > 100:
                status = HealthStatus.WARN
                output = f"Database response time high: {duration_ms}ms"
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.FAIL
            output = f"Database connection failed: {str(e)}"
        
        return HealthCheck(
            name="database",
            status=status,
            time=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            output=output
        )
    
    async def check_redis(self) -> HealthCheck:
        """
        Check Redis connection and basic operations.
        """
        start_time = time.time()
        try:
            redis_service = await get_redis_service()
            # Execute simple command to verify connection
            await redis_service.ping()
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.PASS
            output = "Redis connection successful"
            
            # If operation took too long, mark as warning
            if duration_ms > 50:
                status = HealthStatus.WARN
                output = f"Redis response time high: {duration_ms}ms"
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.FAIL
            output = f"Redis connection failed: {str(e)}"
        
        return HealthCheck(
            name="redis",
            status=status,
            time=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            output=output
        )
    
    async def check_llm_service(self) -> HealthCheck:
        """
        Check LLM service availability.
        """
        start_time = time.time()
        try:
            llm_service = get_llm_service()
            
            # Use a lightweight prompt to test connection
            response = await llm_service.test_connection()
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.PASS
            output = "LLM service connection successful"
            
            # If operation took too long, mark as warning
            if duration_ms > 1000:
                status = HealthStatus.WARN
                output = f"LLM service response time high: {duration_ms}ms"
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status = HealthStatus.FAIL
            output = f"LLM service connection failed: {str(e)}"
        
        return HealthCheck(
            name="llm_service",
            status=status,
            time=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            output=output
        )
    
    async def check_all_components(self) -> List[HealthCheck]:
        """
        Run all component health checks in parallel.
        """
        checks = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_llm_service(),
            self.check_token_service(),
            self.check_deal_service(),
            return_exceptions=True
        )
        
        # Convert any exceptions to failed health checks
        result: List[HealthCheck] = []
        for i, check in enumerate(checks):
            if isinstance(check, Exception):
                component_names = ["database", "redis", "llm_service", "token_service", "deal_service"]
                result.append(HealthCheck(
                    name=component_names[i],
                    status=HealthStatus.FAIL,
                    time=datetime.utcnow().isoformat(),
                    duration_ms=0,
                    output=f"Check failed with exception: {str(check)}"
                ))
            else:
                result.append(check)
        
        return result
```

### Health Check Models

The models used for health check responses:

```python
# health_models.py
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class HealthStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

class HealthCheck(BaseModel):
    name: str
    status: HealthStatus
    time: str
    duration_ms: int
    output: Optional[str] = None

class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    description: str
    checks: List[HealthCheck]
```

## Monitoring Integration

### CloudWatch Configuration

AWS CloudWatch is configured to monitor health check endpoints:

```yaml
# cloudwatch-config.yaml
Resources:
  HealthCheckAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: ApiServiceHealthCheckFailure
      AlarmDescription: API service health check failing
      MetricName: HealthCheckStatus
      Namespace: CustomMetrics/ApiService
      Statistic: Minimum
      Period: 60
      EvaluationPeriods: 2
      Threshold: 1
      ComparisonOperator: LessThanThreshold
      TreatMissingData: breaching
      Dimensions:
        - Name: ServiceName
          Value: agentic-deals-api
      AlarmActions:
        - !Ref AlertTopic
```

### Grafana Dashboard

A Grafana dashboard is provided for visualizing health check metrics:

```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": 10,
  "links": [],
  "panels": [
    {
      "datasource": null,
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [
            {
              "from": "0",
              "id": 1,
              "text": "Failing",
              "to": "0",
              "type": 1,
              "value": "0"
            },
            {
              "from": "1",
              "id": 2,
              "text": "Warning",
              "to": "1",
              "type": 1,
              "value": "1"
            },
            {
              "from": "2",
              "id": 3,
              "text": "Healthy",
              "to": "2",
              "type": 1,
              "value": "2"
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "orange",
                "value": 1
              },
              {
                "color": "green",
                "value": 2
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 9,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "text": {},
        "textMode": "auto"
      },
      "pluginVersion": "7.5.7",
      "targets": [
        {
          "exemplar": true,
          "expr": "health_check_status{service=\"api\"}",
          "interval": "",
          "legendFormat": "",
          "refId": "A"
        }
      ],
      "title": "API Service Health",
      "type": "stat"
    }
  ],
  "schemaVersion": 27,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-6h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Service Health Dashboard",
  "uid": "health_dashboard",
  "version": 1
}
```

## Alerting Configuration

### PagerDuty Integration

Health check failures trigger PagerDuty alerts:

```yaml
# pagerduty-config.yaml
Resources:
  PagerDutyIntegration:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: HealthCheckAlerts
      Subscription:
        - Endpoint: "https://events.pagerduty.com/integration/12345678901234567890/enqueue"
          Protocol: https
```

### Slack Notifications

Health check failures also notify the operations Slack channel:

```yaml
# slack-config.yaml
Resources:
  SlackIntegration:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: SlackHealthAlerts
      Subscription:
        - Endpoint: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
          Protocol: https
```

## Health Check Client

A Python client for programmatically checking service health:

```python
# health_client.py
import aiohttp
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class HealthCheckClient:
    """Client for checking service health endpoints."""
    
    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url
        self.timeout = timeout
    
    async def check_liveness(self) -> Dict[str, Any]:
        """Check service liveness."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/health/live",
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Liveness check failed: HTTP {response.status}")
                        return {
                            "status": "fail",
                            "checks": [
                                {
                                    "name": "http_response",
                                    "status": "fail",
                                    "output": f"HTTP {response.status}"
                                }
                            ]
                        }
            except asyncio.TimeoutError:
                logger.error("Liveness check timed out")
                return {
                    "status": "fail",
                    "checks": [
                        {
                            "name": "http_response",
                            "status": "fail",
                            "output": "Request timed out"
                        }
                    ]
                }
            except Exception as e:
                logger.error(f"Liveness check failed: {str(e)}")
                return {
                    "status": "fail",
                    "checks": [
                        {
                            "name": "http_response",
                            "status": "fail",
                            "output": f"Exception: {str(e)}"
                        }
                    ]
                }
    
    async def check_readiness(self) -> Dict[str, Any]:
        """Check service readiness."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/health/ready",
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Readiness check failed: HTTP {response.status}")
                        return {
                            "status": "fail",
                            "checks": [
                                {
                                    "name": "http_response",
                                    "status": "fail",
                                    "output": f"HTTP {response.status}"
                                }
                            ]
                        }
            except Exception as e:
                logger.error(f"Readiness check failed: {str(e)}")
                return {
                    "status": "fail",
                    "checks": [
                        {
                            "name": "http_response",
                            "status": "fail",
                            "output": f"Exception: {str(e)}"
                        }
                    ]
                }
```

## Best Practices

### Health Check Design

1. **Keep Liveness Checks Lightweight**
   - Should complete within 100ms
   - Avoid database or external service dependencies
   - Use in-memory checks only

2. **Make Readiness Checks Comprehensive**
   - Include all critical dependencies
   - Set appropriate timeouts (1-2 seconds max)
   - Return detailed diagnostic information

3. **Use Appropriate Check Frequency**
   - Liveness: Every 10-30 seconds
   - Readiness: Every 30-60 seconds
   - Deep health: Every 5 minutes

4. **Implement Circuit Breakers**
   - Prevent cascading failures during dependency outages
   - Automatically disable non-critical dependency checks
   - Include circuit breaker status in health check responses

### Security Considerations

1. **Control Access to Detailed Health Information**
   - Use API key authentication for deep health checks
   - Restrict network access to health endpoints
   - Avoid exposing sensitive configuration in health responses

2. **Prevent Denial of Service**
   - Rate limit health check endpoints
   - Use efficient caching for expensive checks
   - Implement timeouts for all external dependency checks

3. **Minimize Information Disclosure**
   - Sanitize error messages in production
   - Avoid exposing internal IP addresses or hostnames
   - Use generic error messages in public endpoints

### Operational Considerations

1. **Alerting Strategy**
   - Configure different alerting thresholds based on check type
   - Use different alert priorities based on impact
   - Implement alert suppression during maintenance windows

2. **Dashboard Visualization**
   - Create dedicated health dashboard
   - Use color-coding for status visualization
   - Include historical health trends

3. **Documentation**
   - Maintain runbooks for common health check failures
   - Document expected values and thresholds
   - Include troubleshooting steps for each component

## Conclusion

Health checks are a critical component of the AI Agentic Deals System's monitoring strategy. By implementing comprehensive health check endpoints with appropriate alerting and visualization, the system can maintain high availability and quickly recover from failures. The health check implementation described in this document balances thoroughness with performance to ensure reliable system monitoring without adding unnecessary overhead.

## References

1. [AWS CloudWatch Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html)
2. [Kubernetes Liveness and Readiness Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
3. [Health Check Response Format for HTTP APIs](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-01)
4. [Monitoring Best Practices](../overview.md) 