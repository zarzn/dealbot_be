"""
WebSocket Lambda Handler for AWS API Gateway

This module provides Lambda function handlers for WebSocket API Gateway routes.
"""

import json
import logging
import os
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

from core.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table(os.environ.get('WEBSOCKET_CONNECTIONS_TABLE', 'websocket-connections'))
messages_table = dynamodb.Table(os.environ.get('WEBSOCKET_MESSAGES_TABLE', 'websocket-messages'))

# Initialize API Gateway Management API client
def get_apigw_management_client(domain_name, stage):
    """Get API Gateway Management API client."""
    endpoint_url = f'https://{domain_name}/{stage}'
    return boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

def handle_connect(event, context):
    """
    Handle WebSocket $connect route.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        dict: Response
    """
    connection_id = event.get('requestContext', {}).get('connectionId')
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    
    if not connection_id:
        logger.error("No connection ID in event")
        return {'statusCode': 400, 'body': 'No connection ID'}
    
    # Extract user ID from query parameters or headers if available
    user_id = None
    if 'queryStringParameters' in event and event['queryStringParameters']:
        user_id = event['queryStringParameters'].get('user_id')
    
    # Store connection in DynamoDB
    try:
        connections_table.put_item(
            Item={
                'connection_id': connection_id,
                'user_id': user_id,
                'connected_at': str(context.aws_request_id),
                'domain_name': domain_name,
                'stage': stage
            }
        )
        logger.info(f"Connection stored: {connection_id} (User: {user_id})")
        return {'statusCode': 200, 'body': 'Connected'}
    except ClientError as e:
        logger.error(f"Error storing connection: {str(e)}")
        return {'statusCode': 500, 'body': 'Error storing connection'}

def handle_disconnect(event, context):
    """
    Handle WebSocket $disconnect route.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        dict: Response
    """
    connection_id = event.get('requestContext', {}).get('connectionId')
    
    if not connection_id:
        logger.error("No connection ID in event")
        return {'statusCode': 400, 'body': 'No connection ID'}
    
    # Remove connection from DynamoDB
    try:
        connections_table.delete_item(
            Key={
                'connection_id': connection_id
            }
        )
        logger.info(f"Connection removed: {connection_id}")
        return {'statusCode': 200, 'body': 'Disconnected'}
    except ClientError as e:
        logger.error(f"Error removing connection: {str(e)}")
        return {'statusCode': 500, 'body': 'Error removing connection'}

def handle_default(event, context):
    """
    Handle WebSocket $default route.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        dict: Response
    """
    connection_id = event.get('requestContext', {}).get('connectionId')
    domain_name = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    
    if not connection_id:
        logger.error("No connection ID in event")
        return {'statusCode': 400, 'body': 'No connection ID'}
    
    # Parse message body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        logger.error("Invalid JSON in message body")
        return {'statusCode': 400, 'body': 'Invalid JSON'}
    
    # Get action from body
    action = body.get('action')
    if not action:
        logger.error("No action in message body")
        return {'statusCode': 400, 'body': 'No action specified'}
    
    # Process message based on action
    try:
        # Get API Gateway Management API client
        apigw_management = get_apigw_management_client(domain_name, stage)
        
        # Process different actions
        if action == 'ping':
            response_data = {
                'action': 'pong',
                'timestamp': body.get('timestamp')
            }
            send_message(apigw_management, connection_id, response_data)
            
        elif action == 'sendMessage':
            # Get message data
            data = body.get('data')
            room_id = body.get('room')
            
            if not data:
                response_data = {
                    'action': 'error',
                    'message': 'Missing data field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing data field'}
            
            # Store message in DynamoDB
            message_id = context.aws_request_id
            messages_table.put_item(
                Item={
                    'message_id': message_id,
                    'connection_id': connection_id,
                    'room_id': room_id,
                    'data': data,
                    'timestamp': body.get('timestamp')
                }
            )
            
            # Broadcast to room if specified, otherwise broadcast to all
            if room_id:
                broadcast_to_room(apigw_management, room_id, {
                    'action': 'messageResponse',
                    'sender': get_user_id_for_connection(connection_id),
                    'data': data,
                    'room': room_id,
                    'timestamp': body.get('timestamp')
                }, exclude_connection_id=None)
            else:
                broadcast_to_all(apigw_management, {
                    'action': 'messageResponse',
                    'sender': get_user_id_for_connection(connection_id),
                    'data': data,
                    'timestamp': body.get('timestamp')
                }, exclude_connection_id=None)
            
            # Send confirmation to sender
            response_data = {
                'action': 'messageSent',
                'message': 'Message sent successfully',
                'data': data,
                'room': room_id,
                'timestamp': body.get('timestamp')
            }
            send_message(apigw_management, connection_id, response_data)
            
        elif action == 'subscribe':
            # Get topic
            topic = body.get('topic')
            
            if not topic:
                response_data = {
                    'action': 'error',
                    'message': 'Missing topic field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing topic field'}
            
            # Subscribe to topic (update DynamoDB)
            connections_table.update_item(
                Key={
                    'connection_id': connection_id
                },
                UpdateExpression='SET topics = list_append(if_not_exists(topics, :empty_list), :topic)',
                ExpressionAttributeValues={
                    ':empty_list': [],
                    ':topic': [topic]
                }
            )
            
            # Send confirmation
            response_data = {
                'action': 'subscribeResponse',
                'success': True,
                'topic': topic,
                'message': 'Subscribed to topic'
            }
            send_message(apigw_management, connection_id, response_data)
            
        elif action == 'unsubscribe':
            # Get topic
            topic = body.get('topic')
            
            if not topic:
                response_data = {
                    'action': 'error',
                    'message': 'Missing topic field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing topic field'}
            
            # Unsubscribe from topic (update DynamoDB)
            # Note: This is a simplified approach. In a real implementation,
            # you would need to find the index of the topic in the list and remove it.
            response_data = {
                'action': 'unsubscribeResponse',
                'success': True,
                'topic': topic,
                'message': 'Unsubscribed from topic'
            }
            send_message(apigw_management, connection_id, response_data)
            
        elif action == 'joinRoom':
            # Get room ID
            room_id = body.get('roomId')
            
            if not room_id:
                response_data = {
                    'action': 'error',
                    'message': 'Missing roomId field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing roomId field'}
            
            # Join room (update DynamoDB)
            connections_table.update_item(
                Key={
                    'connection_id': connection_id
                },
                UpdateExpression='SET rooms = list_append(if_not_exists(rooms, :empty_list), :room)',
                ExpressionAttributeValues={
                    ':empty_list': [],
                    ':room': [room_id]
                }
            )
            
            # Send confirmation
            response_data = {
                'action': 'roomJoined',
                'success': True,
                'roomId': room_id,
                'message': 'Joined room successfully'
            }
            send_message(apigw_management, connection_id, response_data)
            
            # Notify room members
            user_id = get_user_id_for_connection(connection_id)
            broadcast_to_room(apigw_management, room_id, {
                'action': 'userJoined',
                'userId': user_id,
                'roomId': room_id,
                'timestamp': body.get('timestamp')
            }, exclude_connection_id=connection_id)
            
        elif action == 'leaveRoom':
            # Get room ID
            room_id = body.get('roomId')
            
            if not room_id:
                response_data = {
                    'action': 'error',
                    'message': 'Missing roomId field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing roomId field'}
            
            # Leave room (update DynamoDB)
            # Note: This is a simplified approach. In a real implementation,
            # you would need to find the index of the room in the list and remove it.
            response_data = {
                'action': 'roomLeft',
                'success': True,
                'roomId': room_id,
                'message': 'Left room successfully'
            }
            send_message(apigw_management, connection_id, response_data)
            
            # Notify room members
            user_id = get_user_id_for_connection(connection_id)
            broadcast_to_room(apigw_management, room_id, {
                'action': 'userLeft',
                'userId': user_id,
                'roomId': room_id,
                'timestamp': body.get('timestamp')
            }, exclude_connection_id=connection_id)
            
        elif action == 'getPriceUpdate':
            # Get symbol
            symbol = body.get('symbol')
            
            if not symbol:
                response_data = {
                    'action': 'error',
                    'message': 'Missing symbol field'
                }
                send_message(apigw_management, connection_id, response_data)
                return {'statusCode': 400, 'body': 'Missing symbol field'}
            
            # Mock price update for now
            # In production, this would fetch real data
            response_data = {
                'action': 'priceUpdate',
                'symbol': symbol,
                'data': {
                    'price': 123.45,
                    'change': 2.5,
                    'timestamp': body.get('timestamp')
                }
            }
            send_message(apigw_management, connection_id, response_data)
            
        elif action == 'getNotification':
            # Mock notification for now
            # In production, this would fetch real notifications
            response_data = {
                'action': 'notification',
                'data': {
                    'id': 'notif-123',
                    'type': 'alert',
                    'message': 'New deal available',
                    'timestamp': body.get('timestamp')
                }
            }
            send_message(apigw_management, connection_id, response_data)
            
        else:
            # Unknown action
            response_data = {
                'action': 'error',
                'message': f'Unknown action: {action}'
            }
            send_message(apigw_management, connection_id, response_data)
        
        return {'statusCode': 200, 'body': 'Message processed'}
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return {'statusCode': 500, 'body': f'Error processing message: {str(e)}'}

def send_message(apigw_management, connection_id, data):
    """
    Send a message to a connection.
    
    Args:
        apigw_management: API Gateway Management API client
        connection_id: Connection ID
        data: Message data
    """
    try:
        apigw_management.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode('utf-8')
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'GoneException':
            # Connection is gone, remove it from DynamoDB
            try:
                connections_table.delete_item(
                    Key={
                        'connection_id': connection_id
                    }
                )
                logger.info(f"Removed stale connection: {connection_id}")
            except ClientError as e2:
                logger.error(f"Error removing stale connection: {str(e2)}")
        else:
            logger.error(f"Error sending message to {connection_id}: {str(e)}")

def broadcast_to_all(apigw_management, data, exclude_connection_id=None):
    """
    Broadcast a message to all connections.
    
    Args:
        apigw_management: API Gateway Management API client
        data: Message data
        exclude_connection_id: Connection ID to exclude
    """
    try:
        # Scan for all connections
        response = connections_table.scan()
        connections = response.get('Items', [])
        
        # Send message to each connection
        for connection in connections:
            connection_id = connection.get('connection_id')
            if connection_id != exclude_connection_id:
                send_message(apigw_management, connection_id, data)
        
        # Handle pagination if necessary
        while 'LastEvaluatedKey' in response:
            response = connections_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            connections = response.get('Items', [])
            
            for connection in connections:
                connection_id = connection.get('connection_id')
                if connection_id != exclude_connection_id:
                    send_message(apigw_management, connection_id, data)
    except ClientError as e:
        logger.error(f"Error broadcasting message: {str(e)}")

def broadcast_to_room(apigw_management, room_id, data, exclude_connection_id=None):
    """
    Broadcast a message to all connections in a room.
    
    Args:
        apigw_management: API Gateway Management API client
        room_id: Room ID
        data: Message data
        exclude_connection_id: Connection ID to exclude
    """
    try:
        # Scan for connections in the room
        # Note: In a real implementation, you would use a GSI or a more efficient query
        response = connections_table.scan(
            FilterExpression='contains(rooms, :room_id)',
            ExpressionAttributeValues={
                ':room_id': room_id
            }
        )
        connections = response.get('Items', [])
        
        # Send message to each connection
        for connection in connections:
            connection_id = connection.get('connection_id')
            if connection_id != exclude_connection_id:
                send_message(apigw_management, connection_id, data)
        
        # Handle pagination if necessary
        while 'LastEvaluatedKey' in response:
            response = connections_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey'],
                FilterExpression='contains(rooms, :room_id)',
                ExpressionAttributeValues={
                    ':room_id': room_id
                }
            )
            connections = response.get('Items', [])
            
            for connection in connections:
                connection_id = connection.get('connection_id')
                if connection_id != exclude_connection_id:
                    send_message(apigw_management, connection_id, data)
    except ClientError as e:
        logger.error(f"Error broadcasting to room: {str(e)}")

def broadcast_to_topic(apigw_management, topic, data, exclude_connection_id=None):
    """
    Broadcast a message to all connections subscribed to a topic.
    
    Args:
        apigw_management: API Gateway Management API client
        topic: Topic
        data: Message data
        exclude_connection_id: Connection ID to exclude
    """
    try:
        # Scan for connections subscribed to the topic
        # Note: In a real implementation, you would use a GSI or a more efficient query
        response = connections_table.scan(
            FilterExpression='contains(topics, :topic)',
            ExpressionAttributeValues={
                ':topic': topic
            }
        )
        connections = response.get('Items', [])
        
        # Send message to each connection
        for connection in connections:
            connection_id = connection.get('connection_id')
            if connection_id != exclude_connection_id:
                send_message(apigw_management, connection_id, data)
        
        # Handle pagination if necessary
        while 'LastEvaluatedKey' in response:
            response = connections_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey'],
                FilterExpression='contains(topics, :topic)',
                ExpressionAttributeValues={
                    ':topic': topic
                }
            )
            connections = response.get('Items', [])
            
            for connection in connections:
                connection_id = connection.get('connection_id')
                if connection_id != exclude_connection_id:
                    send_message(apigw_management, connection_id, data)
    except ClientError as e:
        logger.error(f"Error broadcasting to topic: {str(e)}")

def get_user_id_for_connection(connection_id):
    """
    Get the user ID for a connection.
    
    Args:
        connection_id: Connection ID
        
    Returns:
        str: User ID or None
    """
    try:
        response = connections_table.get_item(
            Key={
                'connection_id': connection_id
            }
        )
        item = response.get('Item', {})
        return item.get('user_id')
    except ClientError as e:
        logger.error(f"Error getting user ID for connection: {str(e)}")
        return None