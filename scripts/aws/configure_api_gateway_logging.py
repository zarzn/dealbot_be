#!/usr/bin/env python
"""
API Gateway CloudWatch Logging Configuration Script

This script configures CloudWatch logging for REST and WebSocket API Gateways.
It creates the necessary IAM roles, sets up log groups, and enables logging for the API Gateway stages.

Usage:
    python configure_api_gateway_logging.py --rest-api-id API_ID --ws-api-id WS_API_ID --stage STAGE_NAME

Requirements:
    - AWS CLI configured with appropriate credentials
    - boto3 library
"""

import argparse
import boto3
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
logger = logging.getLogger('api_gateway_logging')

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Configure CloudWatch logging for API Gateway')
    parser.add_argument('--rest-api-id', help='REST API Gateway ID')
    parser.add_argument('--ws-api-id', help='WebSocket API Gateway ID')
    parser.add_argument('--stage', required=True, help='API Gateway stage name (e.g., prod, dev)')
    parser.add_argument('--log-level', default='INFO', choices=['ERROR', 'INFO', 'DEBUG'], 
                        help='Log level for API Gateway execution logs')
    parser.add_argument('--region', default=None, help='AWS region (defaults to AWS CLI configuration)')
    
    return parser.parse_args()

def create_iam_role():
    """Create IAM role for API Gateway logging."""
    logger.info("Creating IAM role for API Gateway logging...")
    
    iam = boto3.client('iam')
    role_name = 'APIGatewayCloudWatchLogsRole'
    
    # Check if role already exists
    try:
        response = iam.get_role(RoleName=role_name)
        logger.info(f"IAM role {role_name} already exists")
        return response['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            raise
    
    # Create the role with trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "apigateway.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for API Gateway to write to CloudWatch Logs"
        )
        
        # Attach the CloudWatch Logs policy
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs'
        )
        
        # Wait for the role to propagate
        logger.info("Waiting for IAM role to propagate...")
        time.sleep(10)
        
        logger.info(f"IAM role {role_name} created successfully")
        return response['Role']['Arn']
    except ClientError as e:
        logger.error(f"Error creating IAM role: {e}")
        raise

def configure_rest_api_logging(api_id, stage, role_arn, log_level, region=None):
    """Configure logging for REST API Gateway."""
    if not api_id:
        logger.info("No REST API ID provided, skipping REST API logging configuration")
        return
    
    logger.info(f"Configuring logging for REST API {api_id}, stage {stage}...")
    
    apigateway = boto3.client('apigateway', region_name=region)
    logs = boto3.client('logs', region_name=region)
    
    # Create log group if it doesn't exist
    log_group_name = f"API-Gateway-Execution-Logs_{api_id}/{stage}"
    try:
        logs.create_log_group(logGroupName=log_group_name)
        logger.info(f"Created log group: {log_group_name}")
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
            logger.error(f"Error creating log group: {e}")
            raise
        logger.info(f"Log group {log_group_name} already exists")
    
    # Set retention policy (30 days)
    try:
        logs.put_retention_policy(
            logGroupName=log_group_name,
            retentionInDays=30
        )
        logger.info(f"Set retention policy for log group: {log_group_name}")
    except ClientError as e:
        logger.error(f"Error setting retention policy: {e}")
        raise
    
    # Update stage settings to enable logging
    try:
        apigateway.update_stage(
            restApiId=api_id,
            stageName=stage,
            patchOperations=[
                {
                    'op': 'replace',
                    'path': '/*/*/logging/loglevel',
                    'value': log_level
                },
                {
                    'op': 'replace',
                    'path': '/*/*/logging/dataTrace',
                    'value': 'true'
                },
                {
                    'op': 'replace',
                    'path': '~1~/metrics/enabled',
                    'value': 'true'
                }
            ]
        )
        logger.info(f"Enabled logging for REST API {api_id}, stage {stage}")
    except ClientError as e:
        logger.error(f"Error enabling logging for REST API: {e}")
        raise
    
    # Update account settings to use the IAM role
    try:
        apigateway.update_account(
            patchOperations=[
                {
                    'op': 'replace',
                    'path': '/cloudwatchRoleArn',
                    'value': role_arn
                }
            ]
        )
        logger.info("Updated account settings with CloudWatch role")
    except ClientError as e:
        logger.error(f"Error updating account settings: {e}")
        raise

def configure_websocket_api_logging(api_id, stage, log_level, region=None):
    """Configure logging for WebSocket API Gateway."""
    if not api_id:
        logger.info("No WebSocket API ID provided, skipping WebSocket API logging configuration")
        return
    
    logger.info(f"Configuring logging for WebSocket API {api_id}, stage {stage}...")
    
    apigatewayv2 = boto3.client('apigatewayv2', region_name=region)
    logs = boto3.client('logs', region_name=region)
    
    # Create log group if it doesn't exist
    log_group_name = f"/aws/apigateway/{api_id}/{stage}"
    try:
        logs.create_log_group(logGroupName=log_group_name)
        logger.info(f"Created log group: {log_group_name}")
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
            logger.error(f"Error creating log group: {e}")
            raise
        logger.info(f"Log group {log_group_name} already exists")
    
    # Set retention policy (30 days)
    try:
        logs.put_retention_policy(
            logGroupName=log_group_name,
            retentionInDays=30
        )
        logger.info(f"Set retention policy for log group: {log_group_name}")
    except ClientError as e:
        logger.error(f"Error setting retention policy: {e}")
        raise
    
    # Update stage settings to enable logging
    try:
        # First get current stage
        stage_response = apigatewayv2.get_stage(
            ApiId=api_id,
            StageName=stage
        )
        
        # Prepare default logs settings if none exist
        default_log_settings = {
            'DefaultRouteSettings': {
                'DetailedMetricsEnabled': True,
                'LoggingLevel': log_level,
                'DataTraceEnabled': True,
                'ThrottlingBurstLimit': 5000,
                'ThrottlingRateLimit': 10000
            },
            'AccessLogSettings': {
                'DestinationArn': f"arn:aws:logs:{region or boto3.session.Session().region_name}:{boto3.client('sts').get_caller_identity()['Account']}:log-group:{log_group_name}",
                'Format': '{ "requestId":"$context.requestId", "ip": "$context.identity.sourceIp", "caller":"$context.identity.caller", "user":"$context.identity.user", "requestTime":"$context.requestTime", "routeKey":"$context.routeKey", "status":"$context.status", "connectionId":"$context.connectionId" }'
            }
        }
        
        # Update the stage with logging settings
        apigatewayv2.update_stage(
            ApiId=api_id,
            StageName=stage,
            **default_log_settings
        )
        
        logger.info(f"Enabled logging for WebSocket API {api_id}, stage {stage}")
    except ClientError as e:
        logger.error(f"Error enabling logging for WebSocket API: {e}")
        raise

def main():
    """Main function to configure API Gateway logging."""
    args = parse_arguments()
    
    try:
        # Create the IAM role for API Gateway logging
        role_arn = create_iam_role()
        
        # Configure logging for REST API Gateway
        if args.rest_api_id:
            configure_rest_api_logging(args.rest_api_id, args.stage, role_arn, args.log_level, args.region)
        
        # Configure logging for WebSocket API Gateway
        if args.ws_api_id:
            configure_websocket_api_logging(args.ws_api_id, args.stage, args.log_level, args.region)
        
        logger.info("API Gateway logging configuration completed successfully")
    except Exception as e:
        logger.error(f"Error configuring API Gateway logging: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 