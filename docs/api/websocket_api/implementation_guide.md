# WebSocket API Implementation Guide

This document provides a detailed guide for implementing and using the WebSocket API in the AI Agentic Deals System.

## Table of Contents
1. [Overview](#overview)
2. [AWS API Gateway WebSocket Configuration](#aws-api-gateway-websocket-configuration)
3. [Backend Implementation](#backend-implementation)
4. [Client Implementation](#client-implementation)
5. [Authentication](#authentication)
6. [Message Format](#message-format)
7. [Available Routes](#available-routes)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [Testing](#testing)

## Overview

The WebSocket API enables real-time bidirectional communication between clients and the backend server. This is essential for features such as:

- Real-time deal updates
- Live notifications
- Chat functionality
- Task status updates
- Price updates and alerts

## AWS API Gateway WebSocket Configuration

### Creating the WebSocket API

1. Log in to the AWS Management Console and navigate to API Gateway
2. Click "Create API" and select "WebSocket API"
3. Enter basic information:
   - API name: `aideals-websocket-api`
   - Route selection expression: `$request.body.action`
   - Description: `WebSocket API for AI Agentic Deals System`

### Define Routes

Set up the following routes:

1. **$connect** - Handles client connections
2. **$disconnect** - Handles client disconnections
3. **$default** - Handles messages that don't match other routes
4. **sendMessage** - Handles chat messages
5. **subscribeToDeals** - Subscribes clients to deal updates
6. **notificationAck** - Acknowledges notifications

### Integration Setup

For each route, set up a Lambda integration:

```json
{
  "name": "$connect",
  "integrationUri": "arn:aws:lambda:region:account-id:function:aideals-websocket-connect",
  "integrationType": "AWS_PROXY",
  "templateSelectionExpression": "\\$default",
  "requestTemplates": {
    "$default": "{\"statusCode\": 200}"
  }
}
```

### Deployment

1. Create a stage (e.g., `prod`, `dev`)
2. Deploy the API to the stage
3. Note the WebSocket URL: `wss://api-id.execute-api.region.amazonaws.com/stage`

## Backend Implementation

### Lambda Functions

Create separate Lambda functions for each route:

- `aideals-websocket-connect.py` - Handles connections and authentication
- `aideals-websocket-disconnect.py` - Cleans up resources on disconnect
- `aideals-websocket-default.py` - Handles unmatched route messages
- `aideals-websocket-message.py` - Processes message routes
- `aideals-websocket-subscription.py` - Manages subscriptions

### Connection Handler Example

```python
import json
import boto3
import os
from jwt import decode, InvalidTokenError

# Initialize clients
dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table(os.environ['CONNECTIONS_TABLE_NAME'])

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    
    # Get authentication token from query string
    query_params = event.get('queryStringParameters', {}) or {}
    token = query_params.get('token')
    
    if not token:
        return {
            'statusCode': 401,
            'body': json.dumps('Authentication required')
        }
    
    try:
        # Verify JWT token
        secret_key = os.environ['JWT_SECRET']
        decoded_token = decode(
            token,
            secret_key,
            algorithms=['HS256']
        )
        
        # Store connection in DynamoDB
        connections_table.put_item(
            Item={
                'connectionId': connection_id,
                'userId': decoded_token['sub'],
                'createdAt': int(time.time() * 1000),
                'ttl': int(time.time()) + 86400  # 24-hour TTL
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Connected')
        }
    except InvalidTokenError:
        return {
            'statusCode': 401,
            'body': json.dumps('Invalid authentication token')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps('Internal server error')
        }
```

### Message Sender Utility

Create a utility for sending messages to connected clients:

```python
import boto3
import json
import os

def send_message(connection_id, message_data):
    """Send a message to a connected client."""
    api_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=f"https://{os.environ['API_ID']}.execute-api.{os.environ['REGION']}.amazonaws.com/{os.environ['STAGE']}"
    )
    
    try:
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message_data).encode('utf-8')
        )
        return True
    except Exception as e:
        print(f"Error sending message to {connection_id}: {str(e)}")
        return False
```

### DynamoDB Tables

Create the following DynamoDB tables:

1. **Connections Table**
   - Primary key: `connectionId` (string)
   - Attributes:
     - `userId` (string)
     - `createdAt` (number)
     - `ttl` (number)

2. **Subscriptions Table**
   - Primary key: `subscriptionId` (string)
   - Sort key: `connectionId` (string)
   - Attributes:
     - `userId` (string)
     - `topic` (string)
     - `createdAt` (number)

## Client Implementation

### Browser Client Example

```javascript
class WebSocketClient {
  constructor(url, token) {
    this.url = `${url}?token=${token}`;
    this.callbacks = {};
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 1000;
  }

  connect() {
    this.socket = new WebSocket(this.url);
    
    this.socket.onopen = (event) => {
      console.log('WebSocket connection established');
      this.reconnectAttempts = 0;
      if (this.callbacks.onConnect) {
        this.callbacks.onConnect(event);
      }
    };
    
    this.socket.onclose = (event) => {
      console.log('WebSocket connection closed');
      if (this.callbacks.onDisconnect) {
        this.callbacks.onDisconnect(event);
      }
      
      // Attempt to reconnect
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect();
        }, this.reconnectInterval * this.reconnectAttempts);
      }
    };
    
    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (this.callbacks.onError) {
        this.callbacks.onError(error);
      }
    };
    
    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (this.callbacks.onMessage) {
          this.callbacks.onMessage(message);
        }
        
        // Route to specific message handler if available
        if (message.type && this.callbacks[`on${message.type}`]) {
          this.callbacks[`on${message.type}`](message);
        }
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
  }
  
  send(action, data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message = {
        action,
        data
      };
      this.socket.send(JSON.stringify(message));
      return true;
    }
    return false;
  }
  
  subscribe(topic) {
    return this.send('subscribeToDeals', { topic });
  }
  
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
  
  on(event, callback) {
    this.callbacks[event] = callback;
  }
}

// Usage example
const token = 'your-jwt-token';
const wsClient = new WebSocketClient('wss://api-id.execute-api.region.amazonaws.com/prod', token);

wsClient.on('onConnect', () => {
  console.log('Connected!');
  wsClient.subscribe('new-deals');
});

wsClient.on('onDealUpdate', (message) => {
  console.log('New deal update:', message.data);
  // Update UI with new deal information
});

wsClient.connect();
```

## Authentication

### JWT Authentication

The WebSocket API uses JWT tokens for authentication:

1. **Token Format**: Include the token as a query parameter in the WebSocket URL
   ```
   wss://api-id.execute-api.region.amazonaws.com/prod?token=your-jwt-token
   ```

2. **Token Validation**: Validate the token in the `$connect` route handler
   - Check token expiration
   - Verify signature
   - Extract user ID for authorization

3. **Token Renewal**: Implement token renewal to maintain long-lived connections
   - Send a token refresh message from client when token is about to expire
   - Server responds with a new token
   - Client reconnects with the new token

## Message Format

All WebSocket messages should follow this standard format:

```json
{
  "action": "routeName",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "requestId": "optional-client-request-id"
}
```

Server responses should follow this format:

```json
{
  "type": "messageType",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "requestId": "client-request-id-if-provided",
  "timestamp": 1623456789
}
```

## Available Routes

### 1. sendMessage

Sends a message to another user or a chat room.

**Request:**
```json
{
  "action": "sendMessage",
  "data": {
    "recipientId": "user-id or room-id",
    "content": "Hello, how are you?",
    "type": "text"
  },
  "requestId": "msg-123"
}
```

**Response:**
```json
{
  "type": "messageSent",
  "data": {
    "messageId": "generated-id",
    "status": "delivered",
    "timestamp": 1623456789
  },
  "requestId": "msg-123",
  "timestamp": 1623456789
}
```

### 2. subscribeToDeals

Subscribes the client to deal updates based on criteria.

**Request:**
```json
{
  "action": "subscribeToDeals",
  "data": {
    "topic": "new-deals",
    "filters": {
      "category": "electronics",
      "minDiscount": 20
    }
  },
  "requestId": "sub-456"
}
```

**Response:**
```json
{
  "type": "subscriptionConfirmed",
  "data": {
    "subscriptionId": "generated-id",
    "topic": "new-deals",
    "status": "active"
  },
  "requestId": "sub-456",
  "timestamp": 1623456789
}
```

### 3. notificationAck

Acknowledges receipt of a notification.

**Request:**
```json
{
  "action": "notificationAck",
  "data": {
    "notificationId": "notification-id"
  },
  "requestId": "ack-789"
}
```

**Response:**
```json
{
  "type": "ackConfirmed",
  "data": {
    "notificationId": "notification-id",
    "status": "read"
  },
  "requestId": "ack-789",
  "timestamp": 1623456789
}
```

## Error Handling

### Standard Error Format

All errors should follow this format:

```json
{
  "type": "error",
  "data": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additionalInfo": "Additional error details"
    }
  },
  "requestId": "original-request-id-if-available",
  "timestamp": 1623456789
}
```

### Common Error Codes

- `AUTHENTICATION_ERROR` - Authentication failed
- `AUTHORIZATION_ERROR` - User not authorized to perform action
- `VALIDATION_ERROR` - Invalid message format or data
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server-side error
- `CONNECTION_ERROR` - Connection-related issues

## Best Practices

### Performance Optimization

1. **Message Size**
   - Keep message payloads as small as possible
   - Use pagination for large data sets
   - Consider compression for large messages

2. **Connection Management**
   - Implement connection idle timeout (e.g., 10 minutes)
   - Close unused connections to free up resources
   - Use connection pooling on the server side

3. **Throttling and Rate Limiting**
   - Implement rate limiting for message sending
   - Add backoff logic for reconnection attempts
   - Monitor and adjust limits based on usage patterns

### Security Best Practices

1. **Token Security**
   - Use short-lived tokens (30-60 minutes)
   - Implement token refresh mechanism
   - Store tokens securely on the client side

2. **Message Validation**
   - Validate all incoming messages
   - Sanitize user input to prevent injection attacks
   - Implement message size limits

3. **Access Control**
   - Validate user permissions for each action
   - Implement IP-based restrictions if needed
   - Log all security-related events

## Testing

### Local Testing

For local testing of WebSocket functionality:

1. Use `wscat` for command-line testing:
   ```bash
   wscat -c "wss://api-id.execute-api.region.amazonaws.com/dev?token=your-token"
   ```

2. Send test messages:
   ```json
   {"action":"sendMessage","data":{"recipientId":"user123","content":"Test message"},"requestId":"test-123"}
   ```

### Automated Testing

Implement automated tests for WebSocket functionality:

```python
import pytest
import websocket
import json
import time
import jwt

def get_auth_token(user_id):
    """Generate a test JWT token."""
    payload = {
        'sub': user_id,
        'exp': int(time.time()) + 3600
    }
    return jwt.encode(payload, 'test-secret', algorithm='HS256')

def test_websocket_connection():
    """Test WebSocket connection with authentication."""
    token = get_auth_token('test-user')
    ws = websocket.create_connection(
        f"ws://localhost:3001?token={token}"
    )
    
    # Send a test message
    ws.send(json.dumps({
        'action': 'ping',
        'data': {},
        'requestId': 'test-123'
    }))
    
    # Wait for response
    response = json.loads(ws.recv())
    assert response['type'] == 'pong'
    assert response['requestId'] == 'test-123'
    
    # Clean up
    ws.close()
```

For more detailed examples of client implementations and testing strategies, refer to the [WebSocket Client Examples](client_examples.md) document. 