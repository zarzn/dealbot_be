# API Gateway Testing and Logging Guide

This guide provides instructions for testing API Gateway integrations between frontend and backend, as well as setting up and monitoring CloudWatch logs for API Gateway.

## Table of Contents
1. [Testing API Gateway Integrations](#testing-api-gateway-integrations)
   - [REST API Testing](#rest-api-testing)
   - [WebSocket API Testing](#websocket-api-testing)
   - [End-to-End Testing](#end-to-end-testing)
2. [API Gateway Logging](#api-gateway-logging)
   - [Setting Up CloudWatch Logging](#setting-up-cloudwatch-logging)
   - [Monitoring API Gateway Logs](#monitoring-api-gateway-logs)
3. [Troubleshooting](#troubleshooting)
   - [Common Issues](#common-issues)
   - [CloudWatch Logs Analysis](#cloudwatch-logs-analysis)

## Testing API Gateway Integrations

The project includes several scripts to test the API Gateway integrations between the frontend and backend.

### REST API Testing

Use the `test_api_gateway.ps1` script to test the REST API Gateway integration:

```powershell
# Basic usage
.\backend\scripts\test_api_gateway.ps1 -ApiUrl "https://your-api-id.execute-api.region.amazonaws.com/stage"

# With authentication
.\backend\scripts\test_api_gateway.ps1 -ApiUrl "https://your-api-id.execute-api.region.amazonaws.com/stage" -Username "user@example.com" -Password "password"
```

The script performs the following tests:
- Health check endpoint
- Authentication (if credentials provided)
- User profile retrieval (if authenticated)
- Deals API
- Markets API
- API latency tests

### WebSocket API Testing

Use the `test_websocket_api.ps1` script to test the WebSocket API Gateway integration:

```powershell
# Basic usage
.\backend\scripts\test_websocket_api.ps1 -WebSocketUrl "wss://your-ws-api-id.execute-api.region.amazonaws.com/stage"

# With authentication token
.\backend\scripts\test_websocket_api.ps1 -WebSocketUrl "wss://your-ws-api-id.execute-api.region.amazonaws.com/stage" -AuthToken "your-jwt-token"
```

The script performs the following tests:
- WebSocket connection establishment
- Ping/pong messaging
- Subscription to deal updates
- Status checking

Requirements:
- Node.js installed
- Internet access to download the `ws` package (first run only)

### End-to-End Testing

Use the `test_e2e.ps1` script to perform comprehensive end-to-end testing:

```powershell
# Basic usage with environment variables
.\backend\scripts\test_e2e.ps1

# With explicit URLs
.\backend\scripts\test_e2e.ps1 -RestApiUrl "https://api-id.execute-api.region.amazonaws.com/stage" -WebSocketUrl "wss://ws-api-id.execute-api.region.amazonaws.com/stage" -FrontendUrl "https://your-frontend.example.com"
```

This script combines both REST and WebSocket API testing, and also checks frontend accessibility if a URL is provided.

## API Gateway Logging

### Setting Up CloudWatch Logging

#### 1. Using the Configuration Script

Use the `configure_api_gateway_logging.py` script to enable CloudWatch logging for API Gateway:

```bash
# For REST API Gateway
python backend/scripts/aws/configure_api_gateway_logging.py --rest-api-id your-rest-api-id --stage prod

# For WebSocket API Gateway
python backend/scripts/aws/configure_api_gateway_logging.py --ws-api-id your-websocket-api-id --stage prod

# For both API types
python backend/scripts/aws/configure_api_gateway_logging.py --rest-api-id your-rest-api-id --ws-api-id your-websocket-api-id --stage prod
```

This script performs the following actions:
- Creates the necessary IAM role for API Gateway logging
- Creates CloudWatch log groups
- Sets up log retention (30 days by default)
- Configures API Gateway stages for logging
- Enables detailed metrics

#### 2. Manual Configuration

If you prefer to configure logging manually:

**REST API Gateway**:
1. Navigate to API Gateway in the AWS Console
2. Select your REST API
3. Go to the Stages section and select your stage
4. Under the Logs/Tracing tab:
   - Enable CloudWatch Logs
   - Set Log Level to INFO or DEBUG
   - Enable Detailed Metrics
5. Under Settings, set CloudWatch Log Role ARN to a role with appropriate permissions

**WebSocket API Gateway**:
1. Navigate to API Gateway in the AWS Console
2. Select your WebSocket API
3. Go to the Stages section and select your stage
4. Under Stage settings, enable:
   - Detailed CloudWatch Metrics
   - Default route settings with logging level set to INFO or DEBUG

### Monitoring API Gateway Logs

#### 1. Using the Monitoring Script

Use the `monitor_api_gateway_logs.py` script to view and analyze API Gateway logs:

```bash
# For REST API Gateway
python backend/scripts/aws/monitor_api_gateway_logs.py --api-id your-rest-api-id --stage prod

# For WebSocket API Gateway
python backend/scripts/aws/monitor_api_gateway_logs.py --api-id your-websocket-api-id --stage prod --ws

# Follow logs in real-time (similar to tail -f)
python backend/scripts/aws/monitor_api_gateway_logs.py --api-id your-api-id --stage prod --follow

# Filter logs
python backend/scripts/aws/monitor_api_gateway_logs.py --api-id your-api-id --stage prod --filter "ERROR"

# Save logs to a file
python backend/scripts/aws/monitor_api_gateway_logs.py --api-id your-api-id --stage prod --output logs.txt
```

#### 2. Using AWS Console

To view logs in the AWS Console:
1. Navigate to CloudWatch in the AWS Console
2. Go to Logs > Log groups
3. Find your API Gateway log group:
   - REST API: `API-Gateway-Execution-Logs_{api-id}/{stage}`
   - WebSocket API: `/aws/apigateway/{api-id}/{stage}`
4. Select the log group to view log streams
5. Use the CloudWatch Logs Insights feature for advanced queries

#### 3. Using AWS CLI

To view logs using the AWS CLI:

```bash
# List log groups
aws logs describe-log-groups --log-group-name-prefix API-Gateway-Execution-Logs

# List log streams
aws logs describe-log-streams --log-group-name "API-Gateway-Execution-Logs_your-api-id/prod" --order-by LastEventTime --descending

# Get log events
aws logs get-log-events --log-group-name "API-Gateway-Execution-Logs_your-api-id/prod" --log-stream-name "stream-name"
```

## Troubleshooting

### Common Issues

#### 1. REST API Integration Issues

| Issue | Possible Causes | Troubleshooting Steps |
|-------|----------------|----------------------|
| 403 Forbidden | Missing or incorrect IAM permissions | Check Lambda execution role permissions |
| 502 Bad Gateway | Lambda function error | Check Lambda logs for errors |
| CORS errors | Incorrect CORS configuration | Verify CORS settings in API Gateway |
| Slow response times | Cold starts, inefficient code | Check latency metrics, optimize Lambda code |

#### 2. WebSocket API Issues

| Issue | Possible Causes | Troubleshooting Steps |
|-------|----------------|----------------------|
| Connection failures | Incorrect URL, authentication issues | Verify WebSocket URL, check authentication token |
| Disconnections | Lambda timeouts, client issues | Check Lambda logs, implement reconnection logic |
| Message failures | Incorrect message format | Verify message format matches API expectations |

### CloudWatch Logs Analysis

#### Useful Log Patterns to Look For

**REST API:**
- `Method completed with status:` - Check for non-200 status codes
- `Execution failed due to configuration error` - API Gateway configuration issues
- `Endpoint request timed out` - Lambda function timeout
- `Lambda execution error` - Error in Lambda function

**WebSocket API:**
- `Failed to connect to` - Connection issues
- `WebSocket disconnected (1000)` - Normal disconnection
- `WebSocket disconnected (1001)` - Server closing connection
- `WebSocket disconnected (1006)` - Abnormal closure

#### CloudWatch Logs Insights Queries

Here are some useful CloudWatch Logs Insights queries for analyzing API Gateway logs:

**Find errors in REST API:**
```
filter @message like "ERROR" or @message like "error" or status >= 400
| parse @message /Method completed with status: (?<status_code>\d+)/
| stats count(*) as errorCount by status_code, @logStream
| sort errorCount desc
```

**Analyze API latency:**
```
filter @message like "Method completed with status"
| parse @message /Method completed with status: (?<status_code>\d+), integration latency: (?<integration_latency>[-0-9.]+) ms, method latency: (?<method_latency>[-0-9.]+) ms/
| stats avg(integration_latency) as avgIntegration, avg(method_latency) as avgMethod, max(method_latency) as maxLatency by status_code
| sort avgMethod desc
```

**Monitor WebSocket connections:**
```
filter @message like "WebSocket disconnected" or @message like "WebSocket connected"
| parse @message /"connectionId":"(?<connectionId>[^"]+)"/
| stats count(*) as connectionCount by connectionId
| sort connectionCount desc
```

#### Setting Up CloudWatch Alarms

Configure alarms to notify you of issues:

1. **5XX Error Rate Alarm:**
   - Metric: 5XXError in AWS/ApiGateway
   - Threshold: > 0 for 5 minutes
   - Action: SNS notification

2. **Latency Alarm:**
   - Metric: Latency in AWS/ApiGateway
   - Threshold: > 500ms for 5 minutes
   - Action: SNS notification

3. **WebSocket Connection Count Alarm:**
   - Create a custom metric from logs
   - Count of connection events
   - Threshold: < expected minimum connections
   - Action: SNS notification 