# WebSocket API Documentation

This document provides detailed information about the WebSocket API for the AI Agentic Deals System, which enables real-time communication between the client and server.

## Overview

The WebSocket API allows clients to receive real-time updates about deals, goals, tasks, and other system events without polling the REST API. This improves application responsiveness and reduces server load.

## Connection

### Connection URL

```
wss://api.example.com/ws
```

### Authentication

WebSocket connections require authentication. There are two ways to authenticate:

1. **Query Parameter**: Add the access token as a query parameter:
   ```
   wss://api.example.com/ws?token=your_jwt_token
   ```

2. **Auth Message**: Connect without a token and send an authentication message immediately after connection:
   ```json
   {
     "type": "auth",
     "token": "your_jwt_token"
   }
   ```

Connection will be closed with code `4001` if authentication fails or is not provided within 5 seconds of connection.

## Message Format

All messages follow a standard JSON format with a `type` field indicating the message purpose:

```json
{
  "type": "message_type",
  "data": {
    // Message data specific to the message type
  },
  "id": "optional_message_id"
}
```

- `type`: String identifying the message type
- `data`: Object containing the message payload
- `id`: Optional string to correlate requests with responses

## Subscription Model

Clients can subscribe to specific events using the subscription model:

1. Client sends a subscription request
2. Server acknowledges the subscription
3. Server sends events when they occur
4. Client can unsubscribe when no longer interested

### Subscribe

To subscribe to an event:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "channel_name",
    "params": {
      // Channel-specific parameters
    }
  },
  "id": "request_123"
}
```

### Unsubscribe

To unsubscribe from an event:

```json
{
  "type": "unsubscribe",
  "data": {
    "channel": "channel_name",
    "params": {
      // Same parameters used during subscription
    }
  },
  "id": "request_456"
}
```

## Available Channels

### Deal Updates

Subscribe to updates for a specific deal:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "deal",
    "params": {
      "deal_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

Events for this subscription:

- `deal.updated`: When deal details change
- `deal.score.added`: When a new score is added
- `deal.activity.added`: When a new activity is recorded

Example event:

```json
{
  "type": "deal.updated",
  "data": {
    "deal_id": "123e4567-e89b-12d3-a456-426614174000",
    "changes": {
      "price": 155.75,
      "updated_at": "2023-03-20T15:30:00Z"
    }
  }
}
```

### Goal Updates

Subscribe to updates for a specific goal:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "goal",
    "params": {
      "goal_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

Events for this subscription:

- `goal.updated`: When goal details change
- `goal.status.changed`: When goal status changes
- `goal.task.added`: When a new task is added to the goal

Example event:

```json
{
  "type": "goal.status.changed",
  "data": {
    "goal_id": "123e4567-e89b-12d3-a456-426614174000",
    "old_status": "in_progress",
    "new_status": "completed",
    "updated_at": "2023-03-21T10:15:00Z"
  }
}
```

### Task Updates

Subscribe to updates for a specific task:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "task",
    "params": {
      "task_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

Events for this subscription:

- `task.updated`: When task details change
- `task.status.changed`: When task status changes
- `task.activity.added`: When a new activity is recorded for the task

Example event:

```json
{
  "type": "task.status.changed",
  "data": {
    "task_id": "123e4567-e89b-12d3-a456-426614174000",
    "old_status": "pending",
    "new_status": "in_progress",
    "updated_at": "2023-03-22T09:30:00Z"
  }
}
```

### Agent Updates

Subscribe to updates for a specific agent:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "agent",
    "params": {
      "agent_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

Events for this subscription:

- `agent.status.changed`: When agent status changes
- `agent.task.assigned`: When a task is assigned to the agent
- `agent.message`: When agent sends a message

Example event:

```json
{
  "type": "agent.message",
  "data": {
    "agent_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "I've completed the market analysis for AAPL stock.",
    "timestamp": "2023-03-23T14:45:00Z",
    "context": {
      "task_id": "456e4567-e89b-12d3-a456-426614174000",
      "deal_id": "789e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

### Market Updates

Subscribe to updates for a specific market or symbol:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "market",
    "params": {
      "market_type": "stock",
      "symbol": "AAPL"
    }
  }
}
```

Events for this subscription:

- `market.price.updated`: When price changes
- `market.alert`: When a significant market event occurs

Example event:

```json
{
  "type": "market.price.updated",
  "data": {
    "symbol": "AAPL",
    "market_type": "stock",
    "price": 158.25,
    "change": 2.50,
    "change_percent": 1.60,
    "updated_at": "2023-03-24T15:30:00Z"
  }
}
```

### User Notifications

Subscribe to user-specific notifications:

```json
{
  "type": "subscribe",
  "data": {
    "channel": "notifications"
  }
}
```

Events for this subscription:

- `notification.deal`: Deal-related notifications
- `notification.goal`: Goal-related notifications
- `notification.task`: Task-related notifications
- `notification.system`: System notifications

Example event:

```json
{
  "type": "notification.deal",
  "data": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "Target price reached for AAPL Stock Purchase",
    "level": "info",
    "context": {
      "deal_id": "456e4567-e89b-12d3-a456-426614174000",
      "deal_title": "AAPL Stock Purchase"
    },
    "created_at": "2023-03-25T10:00:00Z",
    "read": false
  }
}
```

## Error Handling

### Error Responses

Error responses follow a standard format:

```json
{
  "type": "error",
  "data": {
    "code": "error_code",
    "message": "Human-readable error message",
    "details": {}
  },
  "id": "original_request_id_if_available"
}
```

### Common Error Codes

| Error Code | Description |
|------------|-------------|
| `auth_required` | Authentication required |
| `auth_failed` | Authentication failed |
| `invalid_request` | Invalid request format |
| `invalid_channel` | Channel does not exist |
| `invalid_params` | Invalid parameters for channel |
| `subscription_failed` | Unable to subscribe to channel |
| `not_found` | Requested resource not found |
| `permission_denied` | Insufficient permissions |
| `rate_limited` | Too many requests |

## Heartbeat

To maintain the WebSocket connection, the server sends a heartbeat message every 30 seconds:

```json
{
  "type": "heartbeat",
  "data": {
    "timestamp": "2023-03-26T12:00:00Z"
  }
}
```

Clients should respond with their own heartbeat within 10 seconds:

```json
{
  "type": "heartbeat",
  "data": {}
}
```

If a client fails to respond to three consecutive heartbeats, the server will close the connection with code `4002`.

## Connection States

The WebSocket connection can be in one of the following states:

1. **Connecting**: Initial state while establishing connection
2. **Authenticating**: Connected but waiting for authentication
3. **Connected**: Authenticated and ready to communicate
4. **Reconnecting**: Attempting to reconnect after disconnection
5. **Disconnected**: Connection closed

## Reconnection Strategy

Clients should implement an exponential backoff strategy for reconnection:

1. First attempt: Immediate
2. Second attempt: Wait 1 second
3. Third attempt: Wait 2 seconds
4. Fourth attempt: Wait 4 seconds
5. Subsequent attempts: Wait up to 30 seconds

Include the last received event ID when reconnecting to avoid missing events:

```json
{
  "type": "auth",
  "token": "your_jwt_token",
  "last_event_id": "evt_12345"
}
```

## Client Implementation Examples

### JavaScript (Browser)

```javascript
class DealsWebSocket {
  constructor(apiUrl, authToken) {
    this.apiUrl = apiUrl;
    this.authToken = authToken;
    this.subscriptions = new Map();
    this.reconnectAttempts = 0;
    this.eventListeners = new Map();
    this.connect();
  }

  connect() {
    this.socket = new WebSocket(`${this.apiUrl}/ws?token=${this.authToken}`);
    
    this.socket.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      
      // Resubscribe to previous channels
      for (let [channel, params] of this.subscriptions.entries()) {
        this.subscribe(channel, params);
      }
    };
    
    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'heartbeat') {
        this.sendHeartbeat();
        return;
      }
      
      // Handle message based on type
      const listeners = this.eventListeners.get(message.type) || [];
      listeners.forEach(callback => callback(message.data));
    };
    
    this.socket.onclose = (event) => {
      console.log(`WebSocket disconnected: ${event.code}`);
      
      if (event.code !== 1000) {
        // 1000 is normal closure
        this.scheduleReconnect();
      }
    };
    
    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }
  
  scheduleReconnect() {
    const delay = Math.min(30000, Math.pow(2, this.reconnectAttempts) * 1000);
    this.reconnectAttempts++;
    
    console.log(`Reconnecting in ${delay}ms...`);
    setTimeout(() => this.connect(), delay);
  }
  
  sendHeartbeat() {
    this.send('heartbeat', {});
  }
  
  send(type, data, id = null) {
    if (this.socket.readyState !== WebSocket.OPEN) {
      console.warn('Cannot send message, socket not open');
      return;
    }
    
    const message = {
      type,
      data,
    };
    
    if (id) {
      message.id = id;
    }
    
    this.socket.send(JSON.stringify(message));
  }
  
  subscribe(channel, params = {}) {
    const subscriptionKey = `${channel}:${JSON.stringify(params)}`;
    this.subscriptions.set(subscriptionKey, params);
    
    this.send('subscribe', {
      channel,
      params
    });
  }
  
  unsubscribe(channel, params = {}) {
    const subscriptionKey = `${channel}:${JSON.stringify(params)}`;
    this.subscriptions.delete(subscriptionKey);
    
    this.send('unsubscribe', {
      channel,
      params
    });
  }
  
  on(eventType, callback) {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, []);
    }
    
    this.eventListeners.get(eventType).push(callback);
  }
  
  off(eventType, callback) {
    if (!this.eventListeners.has(eventType)) {
      return;
    }
    
    const listeners = this.eventListeners.get(eventType);
    const index = listeners.indexOf(callback);
    
    if (index !== -1) {
      listeners.splice(index, 1);
    }
  }
  
  close() {
    if (this.socket) {
      this.socket.close(1000, 'Client initiated close');
    }
  }
}

// Usage example
const socket = new DealsWebSocket('wss://api.example.com', 'your_jwt_token');

// Subscribe to deal updates
socket.subscribe('deal', { deal_id: '123e4567-e89b-12d3-a456-426614174000' });

// Listen for deal updates
socket.on('deal.updated', (data) => {
  console.log('Deal updated:', data);
  updateDealUI(data);
});

// Clean up when done
function cleanup() {
  socket.close();
}
```

### Python

```python
import json
import threading
import time
import websocket

class DealsWebSocket:
    def __init__(self, api_url, auth_token):
        self.api_url = api_url
        self.auth_token = auth_token
        self.subscriptions = {}
        self.reconnect_attempts = 0
        self.event_listeners = {}
        self.ws = None
        self.connect()
    
    def connect(self):
        websocket_url = f"{self.api_url}/ws?token={self.auth_token}"
        self.ws = websocket.WebSocketApp(
            websocket_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Start WebSocket connection in a separate thread
        threading.Thread(target=self.ws.run_forever).start()
    
    def on_open(self, ws):
        print("WebSocket connected")
        self.reconnect_attempts = 0
        
        # Resubscribe to previous channels
        for channel, params in self.subscriptions.items():
            self.subscribe(channel, params)
    
    def on_message(self, ws, message):
        data = json.loads(message)
        
        if data["type"] == "heartbeat":
            self.send_heartbeat()
            return
        
        # Handle message based on type
        event_type = data["type"]
        if event_type in self.event_listeners:
            for callback in self.event_listeners[event_type]:
                callback(data["data"])
    
    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        if close_status_code != 1000:  # 1000 is normal closure
            self.schedule_reconnect()
    
    def schedule_reconnect(self):
        delay = min(30, 2 ** self.reconnect_attempts)
        self.reconnect_attempts += 1
        
        print(f"Reconnecting in {delay} seconds...")
        time.sleep(delay)
        self.connect()
    
    def send_heartbeat(self):
        self.send("heartbeat", {})
    
    def send(self, type, data, id=None):
        if not self.ws:
            print("Cannot send message, socket not connected")
            return
        
        message = {
            "type": type,
            "data": data
        }
        
        if id:
            message["id"] = id
        
        self.ws.send(json.dumps(message))
    
    def subscribe(self, channel, params=None):
        if params is None:
            params = {}
        
        subscription_key = f"{channel}:{json.dumps(params)}"
        self.subscriptions[subscription_key] = params
        
        self.send("subscribe", {
            "channel": channel,
            "params": params
        })
    
    def unsubscribe(self, channel, params=None):
        if params is None:
            params = {}
        
        subscription_key = f"{channel}:{json.dumps(params)}"
        if subscription_key in self.subscriptions:
            del self.subscriptions[subscription_key]
        
        self.send("unsubscribe", {
            "channel": channel,
            "params": params
        })
    
    def on(self, event_type, callback):
        if event_type not in self.event_listeners:
            self.event_listeners[event_type] = []
        
        self.event_listeners[event_type].append(callback)
    
    def off(self, event_type, callback):
        if event_type not in self.event_listeners:
            return
        
        if callback in self.event_listeners[event_type]:
            self.event_listeners[event_type].remove(callback)
    
    def close(self):
        if self.ws:
            self.ws.close()

# Usage example
def update_deal_ui(data):
    print(f"Updating UI for deal {data['deal_id']}")
    # Update UI logic here

# Create WebSocket connection
socket = DealsWebSocket("wss://api.example.com", "your_jwt_token")

# Subscribe to deal updates
socket.subscribe("deal", {"deal_id": "123e4567-e89b-12d3-a456-426614174000"})

# Listen for deal updates
socket.on("deal.updated", update_deal_ui)

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    socket.close()
```

## Best Practices

1. **Handle Reconnection**: Implement robust reconnection logic with exponential backoff
2. **Manage Subscriptions**: Keep track of active subscriptions to restore them after reconnection
3. **Heartbeat Responses**: Always respond to heartbeat messages to keep the connection alive
4. **Error Handling**: Properly handle and log errors
5. **Message Order**: Process messages in the order they are received
6. **Connection Cleanup**: Close the WebSocket connection when no longer needed
7. **Resource Management**: Limit the number of simultaneous WebSocket connections (one per user session is recommended)
8. **Status Tracking**: Implement connection status tracking for your UI

## Rate Limits

To prevent abuse, the WebSocket API has the following rate limits:

- Maximum of 10 simultaneous connections per user
- Maximum of 100 subscriptions per connection
- Maximum of 50 messages sent per minute
- Subscription request rate limit: 20 per minute

When a rate limit is exceeded, the server will send an error message and may disconnect the client if abuse continues.

## Changelog

### Version 1.2 (2023-03-01)
- Added support for market updates channel
- Improved reconnection handling
- Added last_event_id for reconnection

### Version 1.1 (2023-02-15)
- Added agent and task channels
- Improved error handling
- Added heartbeat mechanism

### Version 1.0 (2023-01-30)
- Initial release with deal and goal channels 