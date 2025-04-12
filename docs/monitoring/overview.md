# Monitoring System Overview

## Introduction

This document outlines the monitoring strategy implemented in the AI Agentic Deals System, providing a comprehensive framework for observability, performance tracking, and alerting mechanisms. Our monitoring approach encompasses logging, metrics collection, tracing, and alerting to ensure system health, performance, and reliability.

## Monitoring Architecture

### High-Level Overview

The monitoring architecture follows a layered approach:

1. **Data Collection Layer**: Captures logs, metrics, and traces from all system components
2. **Processing Layer**: Aggregates, filters, and transforms monitoring data
3. **Storage Layer**: Persists monitoring data for analysis and historical reference
4. **Visualization Layer**: Provides dashboards and interfaces for data interpretation
5. **Alerting Layer**: Identifies anomalies and triggers notifications

### Monitoring Components

```
┌────────────────────────────┐    ┌─────────────────────┐    ┌────────────────────┐
│      Application           │    │  Monitoring Stack   │    │   Notification     │
│  ┌──────────┐ ┌──────────┐ │    │  ┌─────────────┐   │    │    Channels        │
│  │ Backend  │ │ Frontend │ │    │  │ CloudWatch  │   │    │  ┌─────────────┐   │
│  │ Services │ │  Apps    │ │──┼─│  │   Logs      │   │    │  │    Email    │   │
│  └──────────┘ └──────────┘ │    │  └─────────────┘   │    │  └─────────────┘   │
│  ┌──────────┐ ┌──────────┐ │    │  ┌─────────────┐   │    │  ┌─────────────┐   │
│  │ Database │ │  Cache   │ │──┼─│  │ CloudWatch  │───┼────│  │    Slack    │   │
│  │ Services │ │ Services │ │    │  │   Metrics   │   │    │  └─────────────┘   │
│  └──────────┘ └──────────┘ │    │  └─────────────┘   │    │  ┌─────────────┐   │
│  ┌──────────┐ ┌──────────┐ │    │  ┌─────────────┐   │    │  │    PagerDuty│   │
│  │   AWS    │ │  Docker  │ │──┼─│  │ CloudWatch  │───┼────│  └─────────────┘   │
│  │ Services │ │ Containers│ │    │  │   Alarms   │   │    │                    │
│  └──────────┘ └──────────┘ │    │  └─────────────┘   │    │                    │
└────────────────────────────┘    └─────────────────────┘    └────────────────────┘
```

## Logging Strategy

### Log Levels and Usage

The system implements a structured logging approach with the following severity levels:

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Detailed information for debugging | `logger.debug("Processing deal with ID: {}", deal_id)` |
| INFO | Confirmation of normal operations | `logger.info("User {} successfully logged in", user_id)` |
| WARNING | Indication of potential issues | `logger.warning("API rate limit at 80% threshold")` |
| ERROR | Error conditions disrupting functionality | `logger.error("Database connection failed: {}", error_message)` |
| CRITICAL | Critical failures requiring immediate attention | `logger.critical("Token service unavailable")` |

### Structured Logging Format

All logs follow a consistent JSON format to enable efficient parsing and analysis:

```json
{
  "timestamp": "2023-07-15T14:22:33.456Z",
  "level": "INFO",
  "service": "deal-analysis-service",
  "trace_id": "4f8b3a2c1d0e9f8a7b6c5d4e",
  "span_id": "1a2b3c4d5e6f7g8h",
  "user_id": "anonymized-if-applicable",
  "message": "Deal analysis completed successfully",
  "additional_data": {
    "deal_id": "deal-123",
    "processing_time_ms": 350,
    "ai_model_used": "gpt-4"
  }
}
```

### Log Collection and Storage

Logs are collected from various components and stored centrally:

1. **Backend Services**: Python logs using the `logging` module with structured JSON formatter
2. **Frontend**: Client-side errors and events captured and sent to backend endpoints
3. **Infrastructure**: AWS CloudWatch Logs for container, database, and other AWS services
4. **Retention Policy**: 
   - Hot storage: 7 days for immediate analysis
   - Warm storage: 30 days for recent troubleshooting
   - Cold storage: 1 year for compliance and historical analysis

### Log Analysis

The system implements:

1. **Real-time log analysis** for immediate issue detection
2. **Log aggregation** to correlate events across services
3. **Search and query capabilities** for troubleshooting
4. **Anomaly detection** for identifying unusual patterns

## Metrics Collection

### Key Metrics Categories

The system collects metrics in the following categories:

1. **System Metrics**:
   - CPU, memory, disk usage, network I/O
   - Container health and resource utilization
   - Database performance (query time, connections, cache hit ratio)

2. **Application Metrics**:
   - Request rates, response times, error rates
   - Endpoint performance and availability
   - Authentication success/failure rates
   - Background job processing rates and times

3. **Business Metrics**:
   - Deal processing volumes and success rates
   - User engagement metrics (searches, saved deals)
   - AI processing times and token consumption
   - Token system transaction volumes and balances

4. **AI-Specific Metrics**:
   - LLM API call volumes and latencies
   - Token usage by model and operation
   - AI analysis accuracy metrics (where measurable)
   - Fallback activation frequency

### Metric Collection Implementation

Metrics are collected using:

1. **CloudWatch Metrics** for AWS infrastructure
2. **Application instrumentation**:
   - Backend: Prometheus client library with FastAPI integration
   - Frontend: Performance API with custom metrics reporting
3. **Custom metrics exporters** for specialized components

### Metric Visualization

Metrics are visualized through:

1. **AWS CloudWatch Dashboards** for infrastructure
2. **Custom operational dashboards** for application performance
3. **Business intelligence dashboards** for business metrics

## Tracing

The system implements distributed tracing to track request flows across services:

1. **OpenTelemetry** integration for trace generation
2. **Trace context propagation** across service boundaries
3. **Span attributes** to capture operation details
4. **Sampling strategy** to balance observability and performance

Example trace context management:
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_deal(deal_id: str):
    with tracer.start_as_current_span("process_deal") as span:
        span.set_attribute("deal.id", deal_id)
        
        # Processing logic
        analysis_result = await analyze_deal(deal_id)
        
        span.set_attribute("processing.status", "completed")
        span.set_attribute("processing.time_ms", processing_time)
        
        return analysis_result
```

## Alerting System

### Alert Categories

Alerts are categorized by severity:

1. **P1 - Critical**: Immediate response required (24/7)
   - System-wide outages
   - Data corruption issues
   - Security breaches

2. **P2 - High**: Prompt response required (business hours + on-call)
   - Service degradation
   - Component failures with business impact
   - Significant performance issues

3. **P3 - Medium**: Normal response (business hours)
   - Non-critical component issues
   - Performance degradation 
   - Error rate increases

4. **P4 - Low**: Scheduled response
   - Minor issues
   - Technical debt indicators
   - Capacity planning warnings

### Alert Configuration

Key alerts configured in the system:

| Alert Name | Trigger Condition | Severity | Response Action |
|------------|-------------------|----------|-----------------|
| API Service Down | API endpoint availability < 99% for 5 minutes | P1 | Immediate intervention, incident response |
| Database High CPU | Database CPU > 80% for 15 minutes | P2 | Performance investigation, query optimization |
| Token Service Errors | Error rate > 5% for 10 minutes | P2 | Service investigation, possible rollback |
| AI Service Latency | 95th percentile latency > 2s for 15 minutes | P3 | Performance investigation, scaling adjustment |

### Alert Notification Channels

Alerts are delivered through multiple channels based on severity:

1. **PagerDuty**: For P1 and P2 alerts requiring immediate attention
2. **Slack**: For all alert levels, with dedicated channels by component 
3. **Email**: Daily and weekly alert summaries
4. **Dashboard**: Real-time alert status visualization

### Alert Response Procedures

Each alert type has documented response procedures:

1. **Acknowledgment protocol**
2. **Investigation checklist**
3. **Remediation steps**
4. **Escalation paths**
5. **Post-incident review requirements**

## Monitoring for Specific Components

### AI Component Monitoring

1. **LLM API Monitoring**:
   - Token usage tracking
   - Response quality metrics
   - Fallback activation frequency

2. **Prompt Performance**:
   - Prompt execution times
   - Token consumption by prompt template
   - Completion quality metrics

3. **AI Agent Behavior**:
   - Decision paths taken
   - Agent interaction patterns
   - Resource consumption patterns

### Token System Monitoring

1. **Transaction Monitoring**:
   - Transaction volumes
   - Success/failure rates
   - Balance verification checks

2. **Balance Monitoring**:
   - User balance distributions
   - System liquidity metrics
   - Reconciliation status

3. **Smart Contract Monitoring**:
   - Contract interaction success rates
   - Gas usage optimization
   - Event emission verification

### Database Monitoring

1. **Performance Metrics**:
   - Query execution times
   - Index utilization
   - Connection pool status

2. **Data Integrity**:
   - Consistency check results
   - Foreign key violation attempts
   - Schema validation status

3. **Capacity Planning**:
   - Storage utilization trends
   - Growth rate projections
   - Scaling threshold alerts

## Setting Up Local Monitoring

For development environments, a simplified monitoring stack is available:

1. **Local Log Collection**:
   ```bash
   # Start local log collection
   docker-compose -f docker-compose.dev.yml up -d log-collector
   ```

2. **Metrics Dashboard**:
   ```bash
   # Start Prometheus and Grafana
   docker-compose -f docker-compose.dev.yml up -d prometheus grafana
   ```

3. **Access Points**:
   - Logs: http://localhost:5601
   - Metrics: http://localhost:3000
   - Traces: http://localhost:16686

## Best Practices

1. **Standardized Instrumentation**:
   - Use consistent naming conventions
   - Implement service-level objectives (SLOs)
   - Follow the RED method (Rate, Errors, Duration)

2. **Optimized Observability**:
   - Use sampling for high-volume telemetry
   - Implement context-aware log levels
   - Balance detail and performance

3. **Actionable Alerting**:
   - Eliminate alert noise through tuning
   - Design alerts based on user impact
   - Include remediation guidance

4. **Documentation**:
   - Maintain up-to-date runbooks
   - Document monitoring coverage
   - Track known patterns and solutions

## References

- [AWS CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Dashboard Examples](https://grafana.com/grafana/dashboards/) 