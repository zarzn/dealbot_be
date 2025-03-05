# WebSocket API Server Implementation Guide

This guide provides detailed instructions for implementing the server-side WebSocket API for the AI Agentic Deals System, focusing on AWS deployment.

## Overview

The AI Agentic Deals System uses a WebSocket API to provide real-time updates, notifications, and messaging capabilities. This guide covers the server-side implementation, including AWS API Gateway configuration, Lambda integration, connection management, and scaling considerations.

## Architecture

The WebSocket API follows this architecture:

```
Client <--> API Gateway (WebSocket) <--> Lambda Functions <--> Backend Services
                                          |
                        Connection data <--> DynamoDB
                                          |
                        Message broker <--> Redis
```

Key components:
- **API Gateway**: Manages WebSocket connections
- **Lambda Functions**: Handle WebSocket events ($connect, $disconnect, message routing)
- **DynamoDB**: Stores connection information
- **Redis**: Handles pub/sub for broadcasting messages

## AWS API Gateway Configuration

### Creating a WebSocket API

1. **Create the API**:
   ```bash
   aws apigatewayv2 create-api \
     --name "AI-Agentic-Deals-WebSocket" \
     --protocol-type WEBSOCKET \
     --route-selection-expression '$request.body.action'
   ```

2. **Note the API ID**:
   ```
   {
     "ApiId": "1ze1jsv3qg",
     "ApiEndpoint": "wss://1ze1jsv3qg.execute-api.us-east-1.amazonaws.com",
     "Name": "AI-Agentic-Deals-WebSocket",
     "ProtocolType": "WEBSOCKET",
     "RouteSelectionExpression": "$request.body.action"
   }
   ```

3. **Create an IAM role for API Gateway**:
   ```bash
   aws iam create-role \
     --role-name APIGatewayWebSocketRole \
     --assume-role-policy-document '{
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Principal": {"Service": "apigateway.amazonaws.com"},
         "Action": "sts:AssumeRole"
       }]
     }'
   ```

4. **Attach policies to the role**:
   ```bash
   aws iam attach-role-policy \
     --role-name APIGatewayWebSocketRole \
     --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs
   
   aws iam attach-role-policy \
     --role-name APIGatewayWebSocketRole \
     --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
   ```

### Required Routes

Create the following routes:

1. **$connect** - Handles new connections
2. **$disconnect** - Handles disconnections
3. **$default** - Handles messages that don't match other routes
4. **Custom routes** - For specific message types (e.g., sendMessage, subscribeToDeals)

Example of creating a route:
```bash
aws apigatewayv2 create-route \
  --api-id 1ze1jsv3qg \
  --route-key '$connect' \
  --target 'integrations/abcd1234'
```

## Lambda Function Implementation

### Connection Management Lambda

```python
import json
import boto3
import os
import jwt
from botocore.exceptions import ClientError

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table(os.environ['CONNECTIONS_TABLE'])

def verify_token(token):
    """Verify the JWT token."""
    try:
        decoded = jwt.decode(
            token, 
            os.environ['JWT_SECRET'], 
            algorithms=[os.environ['JWT_ALGORITHM']]
        )
        return decoded
    except jwt.PyJWTError as e:
        print(f"Token verification failed: {str(e)}")
        return None

def lambda_handler(event, context):
    """Handle WebSocket $connect and $disconnect events."""
    connection_id = event['requestContext']['connectionId']
    route_key = event['requestContext']['routeKey']
    
    # Handle connection
    if route_key == '$connect':
        # Extract the token from the query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        token = query_params.get('token')
        
        if not token:
            return {
                'statusCode': 401,
                'body': json.dumps({'message': 'Authentication token required'})
            }
        
        # Verify the token
        decoded_token = verify_token(token)
        if not decoded_token:
            return {
                'statusCode': 401,
                'body': json.dumps({'message': 'Invalid authentication token'})
            }
        
        # Store the connection in DynamoDB
        try:
            user_id = decoded_token['sub']
            connections_table.put_item(
                Item={
                    'connection_id': connection_id,
                    'user_id': user_id,
                    'connected_at': event['requestContext']['requestTimeEpoch'],
                    'token_exp': decoded_token['exp'],
                    'subscriptions': []
                }
            )
            return {'statusCode': 200, 'body': 'Connected'}
        except ClientError as e:
            print(f"Error storing connection: {str(e)}")
            return {'statusCode': 500, 'body': 'Connection failed'}
    
    # Handle disconnection
    elif route_key == '$disconnect':
        try:
            # Remove the connection from DynamoDB
            connections_table.delete_item(
                Key={'connection_id': connection_id}
            )
            return {'statusCode': 200, 'body': 'Disconnected'}
        except ClientError as e:
            print(f"Error removing connection: {str(e)}")
            return {'statusCode': 500, 'body': 'Disconnection failed'}
    
    # This shouldn't happen
    return {'statusCode': 400, 'body': 'Unhandled route'}
```

### Message Routing Lambda

```python
import json
import boto3
import os
import time
from botocore.exceptions import ClientError

# Initialize clients
dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table(os.environ['CONNECTIONS_TABLE'])
apigateway = boto3.client('apigatewaymanagementapi', 
                         endpoint_url=f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}")
redis_client = boto3.client('elasticache')

def lambda_handler(event, context):
    """Handle WebSocket message routing."""
    connection_id = event['requestContext']['connectionId']
    
    # Parse the message body
    try:
        body = json.loads(event['body'])
        action = body.get('action')
        data = body.get('data', {})
        request_id = body.get('requestId')
    except (json.JSONDecodeError, KeyError):
        send_error(connection_id, 'VALIDATION_ERROR', 'Invalid message format', None)
        return {'statusCode': 400, 'body': 'Bad Request'}
    
    # Get the user information from the connection
    try:
        connection = connections_table.get_item(
            Key={'connection_id': connection_id}
        ).get('Item')
        
        if not connection:
            send_error(connection_id, 'CONNECTION_ERROR', 'Connection not found', request_id)
            return {'statusCode': 400, 'body': 'Connection not found'}
        
        user_id = connection['user_id']
        
        # Check token expiration
        if connection['token_exp'] < int(time.time()):
            send_error(connection_id, 'AUTHENTICATION_ERROR', 'Token expired', request_id)
            return {'statusCode': 401, 'body': 'Token expired'}
            
    except ClientError as e:
        print(f"Error retrieving connection: {str(e)}")
        send_error(connection_id, 'INTERNAL_ERROR', 'Internal server error', request_id)
        return {'statusCode': 500, 'body': 'Internal Server Error'}
    
    # Route the message based on the action
    try:
        if action == 'ping':
            send_message(connection_id, 'pong', {}, request_id)
            return {'statusCode': 200, 'body': 'Pong sent'}
        
        elif action == 'subscribeToDeals':
            return handle_subscribe_to_deals(connection_id, user_id, data, request_id)
        
        elif action == 'unsubscribeFromDeals':
            return handle_unsubscribe_from_deals(connection_id, user_id, data, request_id)
        
        elif action == 'sendMessage':
            return handle_send_message(connection_id, user_id, data, request_id)
        
        elif action == 'notificationAck':
            return handle_notification_ack(connection_id, user_id, data, request_id)
        
        elif action == 'getStatus':
            return handle_get_status(connection_id, user_id, request_id)
        
        else:
            send_error(connection_id, 'VALIDATION_ERROR', f'Unknown action: {action}', request_id)
            return {'statusCode': 400, 'body': 'Unknown action'}
            
    except Exception as e:
        print(f"Error handling message: {str(e)}")
        send_error(connection_id, 'INTERNAL_ERROR', 'Error processing request', request_id)
        return {'statusCode': 500, 'body': 'Internal Server Error'}

def send_message(connection_id, message_type, data, request_id=None):
    """Send a message to a WebSocket client."""
    message = {
        'type': message_type,
        'data': data,
        'timestamp': int(time.time())
    }
    
    if request_id:
        message['requestId'] = request_id
    
    try:
        apigateway.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
        return True
    except apigateway.exceptions.GoneException:
        # Connection is no longer valid
        try:
            connections_table.delete_item(
                Key={'connection_id': connection_id}
            )
        except ClientError:
            pass
        return False
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return False

def send_error(connection_id, error_code, error_message, request_id=None):
    """Send an error message to a WebSocket client."""
    return send_message(
        connection_id, 
        'error', 
        {
            'code': error_code,
            'message': error_message
        },
        request_id
    )

def handle_subscribe_to_deals(connection_id, user_id, data, request_id):
    """Handle subscribing to deals."""
    topic = data.get('topic', 'all-deals')
    filters = data.get('filters', {})
    
    try:
        # Update the connection record with the subscription
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression="SET subscriptions = list_append(subscriptions, :subscription)",
            ExpressionAttributeValues={
                ':subscription': [{
                    'type': 'deal',
                    'topic': topic,
                    'filters': filters
                }]
            }
        )
        
        # Confirm subscription
        send_message(
            connection_id, 
            'subscriptionConfirmed', 
            {
                'topic': topic,
                'filters': filters
            },
            request_id
        )
        
        return {'statusCode': 200, 'body': 'Subscription successful'}
    except Exception as e:
        print(f"Error subscribing to deals: {str(e)}")
        send_error(connection_id, 'SUBSCRIPTION_ERROR', 'Failed to subscribe', request_id)
        return {'statusCode': 500, 'body': 'Subscription failed'}

def handle_unsubscribe_from_deals(connection_id, user_id, data, request_id):
    """Handle unsubscribing from deals."""
    topic = data.get('topic', 'all-deals')
    
    try:
        # Get the current subscriptions
        connection = connections_table.get_item(
            Key={'connection_id': connection_id}
        ).get('Item')
        
        subscriptions = connection.get('subscriptions', [])
        new_subscriptions = [
            sub for sub in subscriptions 
            if not (sub['type'] == 'deal' and sub['topic'] == topic)
        ]
        
        # Update the connection record
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression="SET subscriptions = :subscriptions",
            ExpressionAttributeValues={
                ':subscriptions': new_subscriptions
            }
        )
        
        # Confirm unsubscription
        send_message(
            connection_id, 
            'unsubscriptionConfirmed', 
            {'topic': topic},
            request_id
        )
        
        return {'statusCode': 200, 'body': 'Unsubscription successful'}
    except Exception as e:
        print(f"Error unsubscribing from deals: {str(e)}")
        send_error(connection_id, 'SUBSCRIPTION_ERROR', 'Failed to unsubscribe', request_id)
        return {'statusCode': 500, 'body': 'Unsubscription failed'}

def handle_send_message(connection_id, user_id, data, request_id):
    """Handle sending a message to another user."""
    recipient_id = data.get('recipientId')
    content = data.get('content')
    message_type = data.get('type', 'text')
    
    if not recipient_id or not content:
        send_error(connection_id, 'VALIDATION_ERROR', 'recipientId and content are required', request_id)
        return {'statusCode': 400, 'body': 'Bad Request'}
    
    try:
        # Store the message in the database (implementation depends on your data model)
        # ...
        
        # Find the recipient's connections
        recipient_connections = query_connections_by_user(recipient_id)
        
        # Send the message to all of the recipient's connections
        message_id = f"msg_{int(time.time())}_{request_id}"
        message_data = {
            'messageId': message_id,
            'senderId': user_id,
            'content': content,
            'type': message_type,
            'timestamp': int(time.time())
        }
        
        for conn in recipient_connections:
            send_message(conn['connection_id'], 'messageReceived', message_data)
        
        # Confirm to the sender
        send_message(connection_id, 'messageSent', {
            'messageId': message_id,
            'recipientId': recipient_id,
            'timestamp': int(time.time())
        }, request_id)
        
        return {'statusCode': 200, 'body': 'Message sent'}
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        send_error(connection_id, 'MESSAGE_ERROR', 'Failed to send message', request_id)
        return {'statusCode': 500, 'body': 'Message sending failed'}

def handle_notification_ack(connection_id, user_id, data, request_id):
    """Handle notification acknowledgment."""
    message_id = data.get('messageId')
    ack_type = data.get('type', 'read')
    
    if not message_id:
        send_error(connection_id, 'VALIDATION_ERROR', 'messageId is required', request_id)
        return {'statusCode': 400, 'body': 'Bad Request'}
    
    try:
        # Update the message status in the database (implementation depends on your data model)
        # ...
        
        send_message(connection_id, 'notificationAcked', {
            'messageId': message_id,
            'type': ack_type,
            'timestamp': int(time.time())
        }, request_id)
        
        return {'statusCode': 200, 'body': 'Notification acknowledged'}
    except Exception as e:
        print(f"Error acknowledging notification: {str(e)}")
        send_error(connection_id, 'INTERNAL_ERROR', 'Failed to acknowledge notification', request_id)
        return {'statusCode': 500, 'body': 'Notification acknowledgment failed'}

def handle_get_status(connection_id, user_id, request_id):
    """Handle status request."""
    try:
        # Get the connection data
        connection = connections_table.get_item(
            Key={'connection_id': connection_id}
        ).get('Item')
        
        # Get user data (implementation depends on your data model)
        # ...
        
        send_message(connection_id, 'statusUpdate', {
            'connectionId': connection_id,
            'userId': user_id,
            'connectedSince': connection['connected_at'],
            'subscriptions': connection['subscriptions'],
            'systemStatus': 'operational'
        }, request_id)
        
        return {'statusCode': 200, 'body': 'Status sent'}
    except Exception as e:
        print(f"Error getting status: {str(e)}")
        send_error(connection_id, 'INTERNAL_ERROR', 'Failed to get status', request_id)
        return {'statusCode': 500, 'body': 'Status request failed'}

def query_connections_by_user(user_id):
    """Query for connections by user ID."""
    try:
        # This assumes you have a Global Secondary Index on user_id
        response = connections_table.query(
            IndexName='UserIdIndex',
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={
                ':user_id': user_id
            }
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error querying connections: {str(e)}")
        return []
```

### Broadcast Lambda

This Lambda function is used to broadcast messages to multiple clients.

```python
import json
import boto3
import os
import time
from botocore.exceptions import ClientError

# Initialize clients
dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table(os.environ['CONNECTIONS_TABLE'])
apigateway = boto3.client('apigatewaymanagementapi', 
                         endpoint_url=f"https://{os.environ['API_GATEWAY_ID']}.execute-api.{os.environ['AWS_REGION']}.amazonaws.com/{os.environ['STAGE']}")

def lambda_handler(event, context):
    """Handle broadcasting messages to WebSocket clients."""
    try:
        # Extract the broadcast details from the event
        message_type = event['messageType']
        data = event['data']
        topic = event.get('topic', 'all-deals')
        filters = event.get('filters', {})
        
        # Find connections that are subscribed to this topic
        connections = find_subscribed_connections(topic, filters)
        
        # Broadcast to all matching connections
        success_count = 0
        for conn in connections:
            if send_message(conn['connection_id'], message_type, data):
                success_count += 1
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'broadcast': 'success',
                'delivered': success_count,
                'total': len(connections)
            })
        }
    except Exception as e:
        print(f"Error broadcasting message: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'broadcast': 'failed',
                'error': str(e)
            })
        }

def find_subscribed_connections(topic, filters):
    """Find connections subscribed to a topic with matching filters."""
    try:
        # Scan the connections table for matching subscriptions
        # Note: In a production system, you would use a more efficient approach
        # such as a secondary index or a pub/sub system like Redis
        response = connections_table.scan()
        connections = response.get('Items', [])
        
        # Filter connections by subscription
        matching_connections = []
        for conn in connections:
            for sub in conn.get('subscriptions', []):
                if sub['type'] == 'deal' and sub['topic'] == topic:
                    # Check if filters match (simplified implementation)
                    sub_filters = sub.get('filters', {})
                    if filters_match(sub_filters, filters):
                        matching_connections.append(conn)
                        break
        
        return matching_connections
    except ClientError as e:
        print(f"Error finding subscribed connections: {str(e)}")
        return []

def filters_match(sub_filters, data_filters):
    """Check if subscription filters match the data filters."""
    # This is a simplified implementation
    # In a real-world scenario, you would implement more complex matching logic
    # based on your application's requirements
    
    # If no subscription filters, match everything
    if not sub_filters:
        return True
    
    # For each filter in subscription, check if data matches
    for key, value in sub_filters.items():
        if key in data_filters:
            # Handle array filters
            if isinstance(value, list) and isinstance(data_filters[key], list):
                # Check if any value in the filter list matches any value in the data list
                if not any(v in data_filters[key] for v in value):
                    return False
            # Handle numeric comparisons
            elif key.startswith('min') and float(data_filters[key]) < float(value):
                return False
            elif key.startswith('max') and float(data_filters[key]) > float(value):
                return False
            # Handle direct value comparison
            elif data_filters[key] != value:
                return False
    
    return True

def send_message(connection_id, message_type, data):
    """Send a message to a WebSocket client."""
    message = {
        'type': message_type,
        'data': data,
        'timestamp': int(time.time())
    }
    
    try:
        apigateway.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
        return True
    except apigateway.exceptions.GoneException:
        # Connection is no longer valid
        try:
            connections_table.delete_item(
                Key={'connection_id': connection_id}
            )
        except ClientError:
            pass
        return False
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return False
```

## DynamoDB Table Setup

Create a DynamoDB table to store WebSocket connection information:

```bash
aws dynamodb create-table \
  --table-name WebSocketConnections \
  --attribute-definitions \
    AttributeName=connection_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
  --key-schema AttributeName=connection_id,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --global-secondary-indexes \
    "IndexName=UserIdIndex,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}"
```

## Deployment and Integration

### Deploying the Lambda Functions

1. **Package your Lambda functions**:
   ```bash
   zip -r connection_handler.zip connection_handler.py
   zip -r message_router.zip message_router.py
   zip -r broadcast.zip broadcast.py
   ```

2. **Create IAM roles for Lambda functions**:
   ```bash
   aws iam create-role \
     --role-name WebSocketLambdaRole \
     --assume-role-policy-document '{
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Principal": {"Service": "lambda.amazonaws.com"},
         "Action": "sts:AssumeRole"
       }]
     }'
   ```

3. **Attach policies to the role**:
   ```bash
   aws iam attach-role-policy \
     --role-name WebSocketLambdaRole \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
   
   aws iam attach-role-policy \
     --role-name WebSocketLambdaRole \
     --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
   ```

4. **Create Lambda functions**:
   ```bash
   aws lambda create-function \
     --function-name connection_handler \
     --runtime python3.9 \
     --role arn:aws:iam::123456789012:role/WebSocketLambdaRole \
     --handler connection_handler.lambda_handler \
     --zip-file fileb://connection_handler.zip \
     --environment "Variables={CONNECTIONS_TABLE=WebSocketConnections,JWT_SECRET=your-jwt-secret,JWT_ALGORITHM=HS256}"
   ```

5. **Set up similar commands for the other Lambda functions**

### Integrating with API Gateway

1. **Create integrations**:
   ```bash
   aws apigatewayv2 create-integration \
     --api-id 1ze1jsv3qg \
     --integration-type AWS_PROXY \
     --integration-uri arn:aws:lambda:us-east-1:123456789012:function:connection_handler \
     --payload-format-version 2.0
   ```

2. **Create routes and associate with integrations**:
   ```bash
   aws apigatewayv2 create-route \
     --api-id 1ze1jsv3qg \
     --route-key '$connect' \
     --target "integrations/abcdef"
   ```

3. **Deploy the API**:
   ```bash
   aws apigatewayv2 create-deployment \
     --api-id 1ze1jsv3qg \
     --stage-name prod
   ```

## Invoke URL Configuration

Update the environment variable in your application:

```
WEBSOCKET_API_GATEWAY_URL="wss://1ze1jsv3qg.execute-api.us-east-1.amazonaws.com/prod"
WEBSOCKET_API_GATEWAY_ID="1ze1jsv3qg"
```

## Broadcasting to Clients

### From Backend Services

To broadcast messages from your backend services:

```python
import boto3
import json

lambda_client = boto3.client('lambda')

def broadcast_deal_update(deal_data, topic='new-deals'):
    """Broadcast a deal update to subscribed clients."""
    event = {
        'messageType': 'dealUpdate',
        'data': deal_data,
        'topic': topic,
        'filters': {
            'category': deal_data.get('category'),
            'discount': deal_data.get('discountPercentage')
        }
    }
    
    # Invoke the broadcast Lambda function
    response = lambda_client.invoke(
        FunctionName='broadcast',
        InvocationType='Event',  # Asynchronous invocation
        Payload=json.dumps(event)
    )
    
    return response
```

## Redis Integration for Pub/Sub

For high-scale applications, integrate Redis for more efficient pub/sub:

```python
import redis
import json
import os

# Initialize Redis client
redis_client = redis.Redis(
    host=os.environ['REDIS_HOST'],
    port=int(os.environ['REDIS_PORT']),
    password=os.environ['REDIS_PASSWORD'],
    ssl=True if os.environ['REDIS_SSL'].lower() == 'true' else False
)

def publish_message(channel, message_type, data):
    """Publish a message to a Redis channel."""
    message = {
        'type': message_type,
        'data': data,
        'timestamp': int(time.time())
    }
    
    try:
        redis_client.publish(channel, json.dumps(message))
        return True
    except Exception as e:
        print(f"Error publishing message: {str(e)}")
        return False
```

## Authentication and Security

### JWT Configuration

Ensure your JWT configuration is secure:

1. Use a strong secret key
2. Set appropriate token expiration
3. Include necessary claims (sub, exp, iat)
4. Implement token refresh mechanism

Example JWT configuration:
```python
import jwt
import time
import os

def generate_token(user_id):
    """Generate a JWT token for WebSocket authentication."""
    now = int(time.time())
    payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + (60 * 60),  # 1 hour expiration
        'scope': 'websocket'
    }
    
    return jwt.encode(
        payload,
        os.environ['JWT_SECRET'],
        algorithm=os.environ['JWT_ALGORITHM']
    )
```

### IAM Permissions

Ensure your Lambda functions have minimal required permissions:

- DynamoDB access only to the connections table
- API Gateway execute-api permissions for specific routes
- CloudWatch Logs permissions for logging

## Error Handling and Logging

Implement robust error handling:

1. **Standardize error responses**:
   ```python
   def send_error(connection_id, error_code, error_message, request_id=None):
       """Send a standardized error message to a client."""
       return send_message(
           connection_id, 
           'error', 
           {
               'code': error_code,
               'message': error_message
           },
           request_id
       )
   ```

2. **Log errors to CloudWatch Logs**:
   ```python
   import logging
   
   logger = logging.getLogger()
   logger.setLevel(logging.INFO)
   
   def lambda_handler(event, context):
       try:
           # Function logic
       except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
           # Handle error
   ```

## Scaling Considerations

### API Gateway Limits

Be aware of API Gateway limits:
- Maximum concurrent connections: 10,000 per account
- Message payload size: 128 KB
- Connection duration: 2 hours (implement reconnection)

### DynamoDB Scaling

Configure DynamoDB auto-scaling:
```bash
aws dynamodb update-table \
  --table-name WebSocketConnections \
  --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10
```

### Lambda Concurrency

Set reserved concurrency for Lambda functions:
```bash
aws lambda put-function-concurrency \
  --function-name connection_handler \
  --reserved-concurrent-executions 100
```

## Monitoring and Metrics

### CloudWatch Metrics to Monitor

- ConnectionCount
- MessageCount
- ConnectionDuration
- ErrorRate
- MessageLatency

### Creating CloudWatch Alarms

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name WebSocketConnectionLimitApproaching \
  --alarm-description "Alarm when WebSocket connections approach the limit" \
  --metric-name ConnectionCount \
  --namespace AWS/ApiGateway \
  --dimensions Name=ApiId,Value=1ze1jsv3qg \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 8000 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:WebSocketAlerts
```

## Testing WebSocket API

### Using wscat

```bash
# Install wscat
npm install -g wscat

# Connect to the WebSocket API
wscat -c "wss://1ze1jsv3qg.execute-api.us-east-1.amazonaws.com/prod?token=your-jwt-token"

# Send a test message
{"action":"ping","data":{},"requestId":"test-123"}
```

### AWS CLI Testing

```bash
# Simulate a message
aws apigatewaymanagementapi post-to-connection \
  --endpoint https://1ze1jsv3qg.execute-api.us-east-1.amazonaws.com/prod \
  --connection-id "CONNECTION_ID" \
  --data '{"type":"notification","data":{"title":"Test","message":"This is a test"}}'
```

## Best Practices

1. **Rate Limiting**
   - Implement token bucket algorithm
   - Consider different limits for different actions

2. **Connection Management**
   - Implement heartbeat mechanism
   - Handle reconnections gracefully
   - Cleanup stale connections

3. **Security**
   - Validate all incoming messages
   - Implement proper authentication
   - Use TLS for all communications

4. **Performance**
   - Minimize payload size
   - Use batching for multiple messages
   - Implement efficient filtering

5. **Monitoring**
   - Monitor connection counts
   - Track message volumes
   - Set up alerts for anomalies

## Conclusion

This guide provides a comprehensive framework for implementing a WebSocket API on AWS for the AI Agentic Deals System. By following these instructions, you can create a scalable, secure, and efficient real-time communication system.

For client implementation details, refer to the [WebSocket API Client Guide](client_guide.md) and [WebSocket API Quick Reference](quick_reference.md). 