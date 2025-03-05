#!/usr/bin/env python
"""
API Gateway CloudWatch Logs Monitoring Script

This script monitors CloudWatch logs for API Gateway and displays or saves log entries.
It can be used to troubleshoot integration issues between frontend and backend.

Usage:
    python monitor_api_gateway_logs.py --api-id API_ID --stage STAGE_NAME [--ws] [--output FILE]

Requirements:
    - AWS CLI configured with appropriate credentials
    - boto3 library
"""

import argparse
import boto3
import datetime
import json
import logging
import sys
import time
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api_gateway_logs_monitor')

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Monitor API Gateway CloudWatch logs')
    parser.add_argument('--api-id', required=True, help='API Gateway ID')
    parser.add_argument('--stage', required=True, help='API Gateway stage name (e.g., prod, dev)')
    parser.add_argument('--ws', action='store_true', help='Monitor WebSocket API (default is REST API)')
    parser.add_argument('--filter', default='', help='CloudWatch Logs filter pattern')
    parser.add_argument('--output', help='Output file path (if not specified, logs will be printed)')
    parser.add_argument('--last-minutes', type=int, default=30, 
                        help='Get logs from the last N minutes (default: 30)')
    parser.add_argument('--follow', action='store_true', 
                        help='Keep monitoring logs (similar to tail -f)')
    parser.add_argument('--region', default=None, 
                        help='AWS region (defaults to AWS CLI configuration)')
    
    return parser.parse_args()

def get_log_group_name(api_id, stage, is_ws):
    """Get CloudWatch log group name for API Gateway."""
    if is_ws:
        # WebSocket API log group pattern
        return f"/aws/apigateway/{api_id}/{stage}"
    else:
        # REST API log group pattern
        return f"API-Gateway-Execution-Logs_{api_id}/{stage}"

def get_log_streams(logs_client, log_group_name):
    """Get log streams for the specified log group."""
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=50
        )
        return response.get('logStreams', [])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.error(f"Log group {log_group_name} does not exist. Make sure logging is enabled for this API.")
            return []
        logger.error(f"Error getting log streams: {e}")
        raise

def format_log_event(event, api_type):
    """Format a log event for display."""
    timestamp = datetime.datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    message = event['message'].strip()
    
    # Try to parse and pretty format JSON messages
    try:
        if message.startswith('{') and message.endswith('}'):
            message_json = json.loads(message)
            if api_type == 'ws':
                # Format WebSocket API messages
                if 'connectionId' in message_json:
                    return f"[{timestamp}] ConnectionId: {message_json.get('connectionId', 'N/A')} | " \
                           f"Route: {message_json.get('routeKey', 'N/A')} | " \
                           f"Status: {message_json.get('status', 'N/A')} | " \
                           f"RequestId: {message_json.get('requestId', 'N/A')}"
            else:
                # Format REST API messages
                if 'requestId' in message_json:
                    return f"[{timestamp}] Method: {message_json.get('httpMethod', 'N/A')} | " \
                           f"Path: {message_json.get('path', 'N/A')} | " \
                           f"Status: {message_json.get('status', 'N/A')} | " \
                           f"ResponseTime: {message_json.get('responseLatency', 'N/A')}ms | " \
                           f"RequestId: {message_json.get('requestId', 'N/A')}"
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Default formatting if parsing fails
    return f"[{timestamp}] {message}"

def get_logs(logs_client, log_group_name, start_time, filter_pattern='', log_streams=None, api_type='rest'):
    """Get log events for the specified log group and streams."""
    log_events = []
    
    # If no log streams are specified, get all log streams
    if not log_streams:
        log_streams = get_log_streams(logs_client, log_group_name)
        if not log_streams:
            return log_events
    
    # Convert log streams to stream names
    stream_names = [stream['logStreamName'] for stream in log_streams]
    
    # Get log events for each stream
    for stream_name in stream_names:
        try:
            kwargs = {
                'logGroupName': log_group_name,
                'logStreamName': stream_name,
                'startTime': int(start_time),
                'limit': 1000,
                'startFromHead': True
            }
            
            if filter_pattern:
                kwargs['filterPattern'] = filter_pattern
                
            response = logs_client.get_log_events(**kwargs)
            
            for event in response.get('events', []):
                formatted_event = format_log_event(event, api_type)
                log_events.append(formatted_event)
                
            # Handle pagination if there are more log events
            while 'nextToken' in response and response['nextToken']:
                next_token = response['nextToken']
                response = logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream_name,
                    startTime=int(start_time),
                    nextToken=next_token
                )
                
                for event in response.get('events', []):
                    formatted_event = format_log_event(event, api_type)
                    log_events.append(formatted_event)
                    
        except ClientError as e:
            logger.error(f"Error getting log events for stream {stream_name}: {e}")
    
    # Sort log events by timestamp
    return sorted(log_events)

def monitor_logs(args):
    """Monitor CloudWatch logs for API Gateway."""
    api_id = args.api_id
    stage = args.stage
    is_ws = args.ws
    filter_pattern = args.filter
    output_file = args.output
    last_minutes = args.last_minutes
    follow = args.follow
    region = args.region
    api_type = 'ws' if is_ws else 'rest'
    
    # Initialize CloudWatch Logs client
    logs_client = boto3.client('logs', region_name=region)
    
    # Get log group name
    log_group_name = get_log_group_name(api_id, stage, is_ws)
    logger.info(f"Monitoring logs for {api_type.upper()} API Gateway {api_id}, stage {stage}")
    logger.info(f"Log group: {log_group_name}")
    
    # Calculate start time
    start_time = int((datetime.datetime.now() - datetime.timedelta(minutes=last_minutes)).timestamp() * 1000)
    
    # Open output file if specified
    output = None
    if output_file:
        try:
            output = open(output_file, 'w')
            logger.info(f"Writing logs to {output_file}")
        except IOError as e:
            logger.error(f"Error opening output file: {e}")
            sys.exit(1)
    
    try:
        # Get initial logs
        logger.info(f"Getting logs from the last {last_minutes} minutes...")
        logs = get_logs(logs_client, log_group_name, start_time, filter_pattern, api_type=api_type)
        
        if not logs:
            logger.info("No log events found")
        else:
            logger.info(f"Found {len(logs)} log events")
            for log in logs:
                if output:
                    output.write(log + '\n')
                    output.flush()
                else:
                    print(log)
        
        # If follow mode, keep monitoring for new logs
        if follow:
            logger.info("Monitoring for new logs (Ctrl+C to stop)...")
            while True:
                # Update start time to now minus 1 minute to avoid missing logs
                start_time = int((datetime.datetime.now() - datetime.timedelta(minutes=1)).timestamp() * 1000)
                
                # Wait for new logs
                time.sleep(5)
                
                # Get new logs
                logs = get_logs(logs_client, log_group_name, start_time, filter_pattern, api_type=api_type)
                
                for log in logs:
                    if output:
                        output.write(log + '\n')
                        output.flush()
                    else:
                        print(log)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        if output:
            output.close()

def main():
    """Main function to monitor API Gateway logs."""
    args = parse_arguments()
    
    try:
        monitor_logs(args)
    except Exception as e:
        logger.error(f"Error monitoring API Gateway logs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 