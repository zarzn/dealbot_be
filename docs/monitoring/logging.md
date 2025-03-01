# Monitoring and Logging Guide

## Overview
The AI Agentic Deals System implements comprehensive monitoring and logging to ensure system health, performance, and security. This guide covers logging configuration, monitoring setup, and alerting mechanisms.

## Logging System

### Log Configuration
```python
# core/logger.py

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    """Configure application logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Configure handlers
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Configure loggers
    loggers = {
        'app': logging.INFO,
        'sqlalchemy': logging.WARNING,
        'celery': logging.INFO,
        'redis': logging.WARNING,
        'aiohttp': logging.WARNING
    }

    for logger_name, level in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.addHandler(file_handler)
```

### Log Categories

#### 1. Application Logs
```python
# Example usage
logger = logging.getLogger("app")

logger.info("Application started")
logger.error("Error processing request", extra={
    "request_id": request_id,
    "user_id": user_id,
    "error_details": str(error)
})
```

#### 2. Database Logs
```python
# Database logging configuration
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
```

#### 3. Security Logs
```python
# Security event logging
logger = logging.getLogger("security")

logger.warning("Failed login attempt", extra={
    "ip_address": request.client.host,
    "username": username,
    "timestamp": datetime.utcnow()
})
```

## Monitoring System

### 1. Prometheus Configuration
```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

### 2. Metrics Collection

#### System Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Response time metrics
response_time = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Resource metrics
memory_usage = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes'
)
```

#### Business Metrics
```python
# Deal metrics
deals_found = Counter(
    'deals_found_total',
    'Total deals found',
    ['category', 'source']
)

# Goal metrics
active_goals = Gauge(
    'active_goals',
    'Number of active goals'
)

# Token metrics
token_transactions = Counter(
    'token_transactions_total',
    'Total token transactions',
    ['type', 'status']
)
```

### 3. Grafana Dashboards

#### System Dashboard
```json
{
  "dashboard": {
    "title": "System Overview",
    "panels": [
      {
        "title": "CPU Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(process_cpu_seconds_total[5m])"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "memory_usage_bytes"
          }
        ]
      }
    ]
  }
}
```

#### Business Dashboard
```json
{
  "dashboard": {
    "title": "Business Metrics",
    "panels": [
      {
        "title": "Active Goals",
        "type": "stat",
        "targets": [
          {
            "expr": "active_goals"
          }
        ]
      },
      {
        "title": "Deals Found",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(deals_found_total[1h])"
          }
        ]
      }
    ]
  }
}
```

## Alerting System

### 1. Alert Rules
```yaml
# prometheus/alert.rules
groups:
  - name: system
    rules:
      - alert: HighMemoryUsage
        expr: memory_usage_bytes > 1e9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High memory usage detected

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
```

### 2. Alert Notifications
```python
async def send_alert(alert: Alert):
    """Send alert notification."""
    # Email notification
    await send_email_alert(alert)
    
    # Slack notification
    await send_slack_alert(alert)
    
    # Log alert
    logger.warning("Alert triggered", extra={
        "alert_name": alert.name,
        "severity": alert.severity,
        "details": alert.details
    })
```

## Performance Monitoring

### 1. Response Time Tracking
```python
@app.middleware("http")
async def track_response_time(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    response_time.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response
```

### 2. Database Monitoring
```python
# Database connection pool metrics
db_connections = Gauge(
    'db_connections',
    'Database connections',
    ['state']
)

# Query timing
query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']
)
```

### 3. Cache Monitoring
```python
# Redis metrics
cache_hits = Counter(
    'cache_hits_total',
    'Cache hit count'
)

cache_misses = Counter(
    'cache_misses_total',
    'Cache miss count'
)
```

## Resource Monitoring

### 1. System Resources
```python
# CPU monitoring
cpu_usage = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage'
)

# Disk monitoring
disk_usage = Gauge(
    'disk_usage_bytes',
    'Disk usage in bytes',
    ['mount_point']
)
```

### 2. Application Resources
```python
# Worker monitoring
worker_count = Gauge(
    'celery_workers',
    'Number of Celery workers'
)

# Task monitoring
task_duration = Histogram(
    'task_duration_seconds',
    'Task execution duration',
    ['task_name']
)
```

## Health Checks

### 1. Service Health
```python
@app.get("/health")
async def health_check():
    """Check system health."""
    return {
        "status": "healthy",
        "checks": {
            "database": await check_database(),
            "redis": await check_redis(),
            "celery": await check_celery()
        }
    }
```

### 2. Component Health
```python
async def check_database():
    """Check database health."""
    try:
        await db.execute("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Log Management

### 1. Log Rotation
```python
# Log rotation configuration
log_config = {
    "filename": "app.log",
    "maxBytes": 10_000_000,  # 10MB
    "backupCount": 5,
    "encoding": "utf-8"
}
```

### 2. Log Aggregation
```python
# Centralized logging configuration
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'formatter': 'standard'
        }
    }
}
```

## Best Practices

### 1. Logging
- Use appropriate log levels
- Include context in logs
- Implement structured logging
- Rotate logs regularly
- Monitor log volume

### 2. Monitoring
- Monitor key metrics
- Set up alerting
- Track trends
- Regular review
- Document thresholds

### 3. Alerting
- Define clear thresholds
- Avoid alert fatigue
- Include actionable info
- Regular review
- Document procedures

## Troubleshooting

### Common Issues
1. High memory usage
2. Slow response times
3. Database connection issues
4. Cache performance
5. Worker delays

### Solutions
1. Check resource usage
2. Review error logs
3. Monitor metrics
4. Analyze trends
5. Scale resources 