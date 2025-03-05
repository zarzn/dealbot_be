# WebSocket API Quick Reference

This document provides a quick reference guide for the WebSocket API in the AI Agentic Deals System.

## Connection URL

```
wss://api-id.execute-api.region.amazonaws.com/stage?token=your-jwt-token
```

## Message Format

### Client to Server

```json
{
  "action": "routeName",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "requestId": "client-request-id"
}
```

### Server to Client

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

## Available Actions

| Action | Description | Authentication |
|--------|-------------|----------------|
| `sendMessage` | Send a message to a user or chat room | Required |
| `subscribeToDeals` | Subscribe to deal updates | Required |
| `unsubscribeFromDeals` | Unsubscribe from deal updates | Required |
| `notificationAck` | Acknowledge a notification | Required |
| `getStatus` | Get connection status | Required |
| `ping` | Check connection | Optional |

## Message Types (Server to Client)

| Type | Description |
|------|-------------|
| `dealUpdate` | New or updated deal information |
| `notification` | System notification |
| `messageSent` | Confirmation of sent message |
| `messageReceived` | New message received |
| `subscriptionConfirmed` | Subscription confirmation |
| `unsubscriptionConfirmed` | Unsubscription confirmation |
| `statusUpdate` | Connection or system status update |
| `error` | Error response |
| `pong` | Response to ping |

## Common Patterns

### Authentication

1. Obtain JWT token from `/api/auth/login` endpoint
2. Connect to WebSocket with token as query parameter
3. Handle reconnection if token expires

### Deal Subscription

```javascript
// Subscribe to deals
socket.send(JSON.stringify({
  action: "subscribeToDeals",
  data: {
    topic: "new-deals",
    filters: {
      category: "electronics",
      minDiscount: 20
    }
  },
  requestId: "sub-123"
}));

// Handle deal updates
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "dealUpdate") {
    // Process deal update
    console.log("New deal:", message.data);
  }
};
```

### Sending Messages

```javascript
// Send a message
socket.send(JSON.stringify({
  action: "sendMessage",
  data: {
    recipientId: "user123",
    content: "Hello, how are you?",
    type: "text"
  },
  requestId: "msg-456"
}));

// Handle sent confirmation
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "messageSent" && message.requestId === "msg-456") {
    console.log("Message sent successfully:", message.data.messageId);
  }
};
```

### Error Handling

```javascript
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === "error") {
    console.error("Error:", message.data.code, message.data.message);
    
    // Handle specific errors
    if (message.data.code === "AUTHENTICATION_ERROR") {
      // Reconnect with new token
      getNewToken().then(newToken => reconnect(newToken));
    }
  }
};
```

## Rate Limits

| Action | Rate Limit |
|--------|------------|
| Connect | 5 per minute |
| Send Message | 10 per minute |
| Subscribe | 5 per minute |
| All Other Actions | 20 per minute |

## Error Codes

| Code | Description |
|------|-------------|
| `AUTHENTICATION_ERROR` | Authentication failed |
| `AUTHORIZATION_ERROR` | Not authorized to perform action |
| `VALIDATION_ERROR` | Invalid message format or data |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INTERNAL_ERROR` | Server-side error |
| `CONNECTION_ERROR` | Connection-related issues |
| `SUBSCRIPTION_ERROR` | Error in subscription process |
| `MESSAGE_ERROR` | Error in message processing |

## Testing WebSocket API

### Using wscat

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket API
wscat -c "wss://api-id.execute-api.region.amazonaws.com/dev?token=your-jwt-token"

# Send a test message
{"action":"ping","data":{},"requestId":"test-123"}
```

### Response Example

```json
{
  "type": "pong",
  "data": {},
  "requestId": "test-123",
  "timestamp": 1623456789
}
```

For more detailed information, refer to the [WebSocket API Implementation Guide](implementation_guide.md). 