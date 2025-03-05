# WebSocket API Client Implementation Guide

This guide provides detailed instructions for implementing client-side WebSocket connectivity with the AI Agentic Deals System.

## Overview

The AI Agentic Deals System uses WebSockets to provide real-time updates for deals, notifications, and chat messages. This guide will help you implement a robust client-side WebSocket connection that handles authentication, reconnection, and message processing.

## Prerequisites

- Understanding of WebSocket protocol
- Familiarity with JavaScript/TypeScript
- Valid JWT token from the authentication API

## Basic Implementation

### Establishing a Connection

```javascript
class DealsWebSocketClient {
  constructor(baseUrl, authToken) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 2000; // 2 seconds
    this.messageHandlers = new Map();
    this.pendingRequests = new Map();
  }

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket connection already exists');
      return;
    }

    const url = `${this.baseUrl}?token=${this.authToken}`;
    this.socket = new WebSocket(url);

    this.socket.onopen = this.handleOpen.bind(this);
    this.socket.onmessage = this.handleMessage.bind(this);
    this.socket.onclose = this.handleClose.bind(this);
    this.socket.onerror = this.handleError.bind(this);
  }

  handleOpen(event) {
    console.log('WebSocket connection established');
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.onConnected && this.onConnected();
  }

  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      console.log('WebSocket message received:', message);
      
      // Handle pending requests
      if (message.requestId && this.pendingRequests.has(message.requestId)) {
        const { resolve, reject } = this.pendingRequests.get(message.requestId);
        if (message.type === 'error') {
          reject(new Error(message.data.message));
        } else {
          resolve(message);
        }
        this.pendingRequests.delete(message.requestId);
      }
      
      // Process message by type
      if (this.messageHandlers.has(message.type)) {
        this.messageHandlers.get(message.type)(message);
      }
      
      // Global message handler
      this.onMessage && this.onMessage(message);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  handleClose(event) {
    console.log(`WebSocket connection closed: ${event.code} ${event.reason}`);
    this.isConnected = false;
    this.onDisconnected && this.onDisconnected(event);
    
    // Attempt to reconnect if the close wasn't intentional
    if (event.code !== 1000) {
      this.attemptReconnect();
    }
  }

  handleError(error) {
    console.error('WebSocket error:', error);
    this.onError && this.onError(error);
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Maximum reconnection attempts reached');
      return;
    }
    
    this.reconnectAttempts++;
    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
    
    setTimeout(() => {
      this.connect();
    }, this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1)); // Exponential backoff
  }

  disconnect() {
    if (this.socket) {
      this.socket.close(1000, 'Client disconnected');
      this.socket = null;
      this.isConnected = false;
    }
  }

  // Register a handler for a specific message type
  on(messageType, callback) {
    this.messageHandlers.set(messageType, callback);
    return this;
  }

  // Remove a handler
  off(messageType) {
    this.messageHandlers.delete(messageType);
    return this;
  }

  // Send a message to the server
  send(action, data = {}, requestId = null) {
    if (!this.isConnected) {
      return Promise.reject(new Error('WebSocket is not connected'));
    }
    
    const id = requestId || `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const message = JSON.stringify({
      action,
      data,
      requestId: id
    });
    
    return new Promise((resolve, reject) => {
      try {
        this.socket.send(message);
        
        // Store the promise callbacks to resolve when we get a response
        this.pendingRequests.set(id, { resolve, reject });
        
        // Set a timeout to reject the promise if no response is received
        setTimeout(() => {
          if (this.pendingRequests.has(id)) {
            this.pendingRequests.delete(id);
            reject(new Error('Request timed out'));
          }
        }, 10000); // 10 second timeout
      } catch (error) {
        reject(error);
      }
    });
  }

  // Helper method for pinging the server
  ping() {
    return this.send('ping', {});
  }
}
```

### Usage Example

```javascript
// Initialize the client
const client = new DealsWebSocketClient(
  'wss://api-id.execute-api.region.amazonaws.com/dev',
  'your-jwt-token'
);

// Register event handlers
client.onConnected = () => {
  console.log('Connection established, subscribing to deals...');
  client.send('subscribeToDeals', {
    topic: 'flash-deals'
  });
};

client.onDisconnected = (event) => {
  console.log('Disconnected from server:', event);
};

client.onError = (error) => {
  console.error('WebSocket error:', error);
};

// Register message type handlers
client.on('dealUpdate', (message) => {
  console.log('New deal available:', message.data);
  updateUIWithNewDeal(message.data);
});

client.on('notification', (message) => {
  showNotification(message.data.title, message.data.message);
});

// Connect to the WebSocket server
client.connect();

// Later, to disconnect
// client.disconnect();
```

## Advanced Features

### Token Refresh and Reconnection

```javascript
class DealsWebSocketClientWithAuth extends DealsWebSocketClient {
  constructor(baseUrl, authToken, refreshTokenCallback) {
    super(baseUrl, authToken);
    this.refreshTokenCallback = refreshTokenCallback;
  }

  async handleTokenExpiration() {
    try {
      // Get a new token
      const newToken = await this.refreshTokenCallback();
      this.authToken = newToken;
      
      // Reconnect with the new token
      this.disconnect();
      this.connect();
      return true;
    } catch (error) {
      console.error('Failed to refresh token:', error);
      return false;
    }
  }

  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      
      // Check for authentication errors
      if (message.type === 'error' && 
          (message.data.code === 'AUTHENTICATION_ERROR' || 
           message.data.code === 'TOKEN_EXPIRED')) {
        this.handleTokenExpiration();
        return;
      }
      
      // Continue with normal message handling
      super.handleMessage(event);
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
    }
  }
}

// Usage
const client = new DealsWebSocketClientWithAuth(
  'wss://api-id.execute-api.region.amazonaws.com/dev',
  initialToken,
  async () => {
    // Implement your token refresh logic here
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        refreshToken: yourRefreshToken
      })
    });
    
    const data = await response.json();
    return data.token;
  }
);
```

### Subscribing to Deal Updates

```javascript
// Subscribe to specific deal categories
client.send('subscribeToDeals', {
  topic: 'deals',
  filters: {
    categories: ['electronics', 'home-appliances'],
    minDiscount: 20,
    maxPrice: 500
  }
})
.then(response => {
  console.log('Successfully subscribed to deals:', response);
})
.catch(error => {
  console.error('Failed to subscribe to deals:', error);
});
```

### Sending and Receiving Chat Messages

```javascript
// Send a message
client.send('sendMessage', {
  recipientId: 'user123',
  content: 'Hello, is this deal still available?',
  type: 'text',
  dealId: 'deal456'
})
.then(response => {
  console.log('Message sent successfully:', response);
})
.catch(error => {
  console.error('Failed to send message:', error);
});

// Handle incoming messages
client.on('messageReceived', (message) => {
  const { senderId, content, timestamp, type } = message.data;
  
  // Add message to chat UI
  addMessageToConversation(senderId, content, new Date(timestamp), type);
  
  // Send read receipt
  client.send('notificationAck', {
    messageId: message.data.messageId,
    type: 'read'
  });
});
```

## React Implementation

Here's an example of implementing the WebSocket client in a React application:

```jsx
import React, { useEffect, useState, useContext, createContext } from 'react';

// Create WebSocket context
const WebSocketContext = createContext(null);

// WebSocket provider component
export const WebSocketProvider = ({ children, baseUrl, authToken }) => {
  const [client, setClient] = useState(null);
  const [connected, setConnected] = useState(false);
  const [deals, setDeals] = useState([]);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    // Create WebSocket client
    const wsClient = new DealsWebSocketClient(baseUrl, authToken);
    
    wsClient.onConnected = () => {
      setConnected(true);
      
      // Subscribe to relevant topics
      wsClient.send('subscribeToDeals', { topic: 'all-deals' });
      wsClient.send('subscribeToDeals', { topic: 'user-notifications' });
    };
    
    wsClient.onDisconnected = () => {
      setConnected(false);
    };
    
    // Set up message handlers
    wsClient.on('dealUpdate', (message) => {
      setDeals(prev => [...prev, message.data]);
    });
    
    wsClient.on('notification', (message) => {
      setNotifications(prev => [...prev, message.data]);
    });
    
    // Connect to WebSocket server
    wsClient.connect();
    setClient(wsClient);
    
    // Clean up on unmount
    return () => {
      wsClient.disconnect();
    };
  }, [baseUrl, authToken]);

  // Methods for components to use
  const sendMessage = (recipientId, content, type = 'text') => {
    if (!client || !connected) return Promise.reject(new Error('Not connected'));
    
    return client.send('sendMessage', { recipientId, content, type });
  };
  
  const subscribeToDeals = (filters) => {
    if (!client || !connected) return Promise.reject(new Error('Not connected'));
    
    return client.send('subscribeToDeals', { 
      topic: 'filtered-deals',
      filters
    });
  };
  
  // Context value
  const value = {
    connected,
    deals,
    notifications,
    sendMessage,
    subscribeToDeals,
    client // Expose the client for advanced usage
  };
  
  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Hook for consuming the WebSocket context
export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

// Example usage in a component
const DealsComponent = () => {
  const { deals, connected, subscribeToDeals } = useWebSocket();
  const [filteredDeals, setFilteredDeals] = useState([]);
  const [filter, setFilter] = useState({ category: 'all', minDiscount: 0 });

  useEffect(() => {
    // Filter deals locally
    setFilteredDeals(deals.filter(deal => {
      if (filter.category !== 'all' && deal.category !== filter.category) {
        return false;
      }
      if (deal.discountPercentage < filter.minDiscount) {
        return false;
      }
      return true;
    }));
  }, [deals, filter]);

  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
    
    // Also update server-side filter (if connected)
    if (connected) {
      subscribeToDeals(newFilter)
        .then(() => console.log('Filter updated'))
        .catch(err => console.error('Failed to update filter', err));
    }
  };

  return (
    <div>
      <div className="status">
        {connected ? 'Connected: Receiving live updates' : 'Disconnected'}
      </div>
      
      <div className="filters">
        <select 
          value={filter.category}
          onChange={e => handleFilterChange({...filter, category: e.target.value})}
        >
          <option value="all">All Categories</option>
          <option value="electronics">Electronics</option>
          <option value="fashion">Fashion</option>
          <option value="home">Home & Garden</option>
        </select>
        
        <input 
          type="range" 
          min="0" 
          max="90" 
          value={filter.minDiscount}
          onChange={e => handleFilterChange({...filter, minDiscount: Number(e.target.value)})}
        />
        <span>Min Discount: {filter.minDiscount}%</span>
      </div>
      
      <div className="deals-list">
        {filteredDeals.length === 0 ? (
          <p>No deals found matching your criteria</p>
        ) : (
          filteredDeals.map(deal => (
            <div key={deal.id} className="deal-card">
              <h3>{deal.title}</h3>
              <p>{deal.description}</p>
              <div className="price">
                <span className="original">${deal.originalPrice}</span>
                <span className="current">${deal.currentPrice}</span>
                <span className="discount">{deal.discountPercentage}% off</span>
              </div>
              <button>View Deal</button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
```

## Troubleshooting

### Common Issues and Solutions

#### Connection Issues

- **Issue**: Unable to establish connection
  - **Solution**: Verify the WebSocket URL is correct and that your JWT token is valid
  - **Solution**: Check network connectivity and firewall settings

- **Issue**: Frequent disconnections
  - **Solution**: Implement exponential backoff for reconnection attempts
  - **Solution**: Ensure stable network connection
  - **Solution**: Check server-side connection limits

#### Authentication Issues

- **Issue**: Authentication errors after connecting
  - **Solution**: Implement token refresh logic
  - **Solution**: Ensure correct token format (Bearer prefix may be required)

#### Message Handling Issues

- **Issue**: Messages not being processed
  - **Solution**: Verify message format matches expected schema
  - **Solution**: Check event handler registration
  - **Solution**: Implement proper error handling in message processing

### Debugging WebSocket Connections

```javascript
// Add this to your WebSocket client for enhanced debugging
class DebuggableWebSocketClient extends DealsWebSocketClient {
  constructor(baseUrl, authToken, debugLevel = 'info') {
    super(baseUrl, authToken);
    this.debugLevel = debugLevel;
  }
  
  log(level, ...args) {
    const levels = {
      error: 0,
      warn: 1,
      info: 2,
      debug: 3
    };
    
    if (levels[level] <= levels[this.debugLevel]) {
      console[level](`[WebSocket][${new Date().toISOString()}]`, ...args);
    }
  }
  
  connect() {
    this.log('info', 'Connecting to', this.baseUrl);
    super.connect();
  }
  
  handleOpen(event) {
    this.log('info', 'Connection established');
    super.handleOpen(event);
  }
  
  handleMessage(event) {
    this.log('debug', 'Message received:', event.data);
    super.handleMessage(event);
  }
  
  handleClose(event) {
    this.log('warn', `Connection closed: ${event.code} ${event.reason}`);
    super.handleClose(event);
  }
  
  handleError(error) {
    this.log('error', 'WebSocket error:', error);
    super.handleError(error);
  }
  
  send(action, data = {}, requestId = null) {
    this.log('debug', 'Sending message:', { action, data, requestId });
    return super.send(action, data, requestId);
  }
}

// Usage
const client = new DebuggableWebSocketClient(
  'wss://api-id.execute-api.region.amazonaws.com/dev',
  'your-jwt-token',
  'debug' // Set to 'error', 'warn', 'info', or 'debug'
);
```

## Best Practices

1. **Implement Robust Error Handling**
   - Handle all possible WebSocket events (open, message, close, error)
   - Use try/catch blocks when processing messages
   - Provide fallback mechanisms for critical operations

2. **Manage Reconnection Properly**
   - Use exponential backoff for reconnection attempts
   - Limit the maximum number of reconnection attempts
   - Clear and reset state appropriately on reconnection

3. **Optimize Message Size**
   - Keep messages as small as possible
   - Consider compressing large messages
   - Batch related updates when appropriate

4. **Ensure Security**
   - Always use secure WebSocket connections (wss://)
   - Implement proper token validation and renewal
   - Sanitize and validate all input data

5. **Monitor Connection Health**
   - Implement a ping/pong mechanism to detect stale connections
   - Set up proper timeouts for operations
   - Log connection metrics for analysis

6. **Structure Code for Maintainability**
   - Separate WebSocket logic from application logic
   - Use event-based architecture for message handling
   - Document all message formats and expected responses

## Additional Resources

- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [AWS API Gateway WebSockets](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)

For the complete API specification, refer to the [WebSocket API Implementation Guide](implementation_guide.md) and [WebSocket API Quick Reference](quick_reference.md). 