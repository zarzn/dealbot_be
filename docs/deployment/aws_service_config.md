# AWS Service Configuration

This document outlines the AWS service configuration for the AI Agentic Deals System, including how environment variables are loaded from AWS services and how the health check system works.

## Environment Variables and Secrets

The application supports loading environment variables from two AWS services:

1. **AWS Secrets Manager (Preferred)** - Primary source for secrets and configuration
2. **AWS Parameter Store (Optional)** - Secondary source, disabled by default

### AWS Secrets Manager Configuration

Secrets Manager is used for storing sensitive credentials and configuration parameters. The application will look for secrets in the following structure:

```
aideals/{environment}/secrets
```

Where `{environment}` is one of:
- `production`
- `staging`
- `development`

#### Required Secret Keys

The following keys are expected to be defined in the secret:

- `POSTGRES_PASSWORD` - Database password
- `REDIS_PASSWORD` - Redis password
- `SECRET_KEY` - Application secret key
- `JWT_SECRET` - JWT signing secret
- `DEEPSEEK_API_KEY` - DeepSeek API key
- `OPENAI_API_KEY` - OpenAI API key

Example secret structure:
```json
{
  "POSTGRES_PASSWORD": "your-secure-db-password",
  "REDIS_PASSWORD": "your-secure-redis-password",
  "SECRET_KEY": "your-secure-application-key",
  "JWT_SECRET": "your-secure-jwt-key",
  "DEEPSEEK_API_KEY": "your-deepseek-api-key",
  "OPENAI_API_KEY": "your-openai-api-key"
}
```

#### Creating AWS Secrets Manager Secret

Use the AWS CLI or Console to create the secret:

```bash
aws secretsmanager create-secret \
  --name aideals/production/secrets \
  --description "AI Agentic Deals System production secrets" \
  --secret-string "{\"POSTGRES_PASSWORD\":\"your-secure-db-password\",\"REDIS_PASSWORD\":\"your-secure-redis-password\",\"SECRET_KEY\":\"your-secure-application-key\",\"JWT_SECRET\":\"your-secure-jwt-key\",\"DEEPSEEK_API_KEY\":\"your-deepseek-api-key\",\"OPENAI_API_KEY\":\"your-openai-api-key\"}"
```

### AWS Parameter Store Configuration

Parameter Store can be used for non-sensitive configuration parameters. The application will look for parameters with the following path structure:

```
/aideals/{environment}/{parameter_name}
```

#### Required Parameters

The following parameters are expected to be defined:

- `/aideals/production/POSTGRES_HOST` - Database host
- `/aideals/production/POSTGRES_PORT` - Database port
- `/aideals/production/POSTGRES_DB` - Database name
- `/aideals/production/REDIS_HOST` - Redis host
- `/aideals/production/REDIS_PORT` - Redis port

#### Creating AWS Parameter Store Parameters

Use the AWS CLI or Console to create the parameters:

```bash
aws ssm put-parameter \
  --name "/aideals/production/POSTGRES_HOST" \
  --value "your-db-host.rds.amazonaws.com" \
  --type "String" \
  --description "Database host for AI Agentic Deals System"
```

## ECS Task Definition Integration

To make environment variables available to your ECS tasks, configure them in the task definition:

```json
{
  "containerDefinitions": [
    {
      "name": "aideals-api",
      "image": "...",
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "DEBUG",
          "value": "false"
        }
      ],
      "secrets": [
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:aideals/production/secrets:POSTGRES_PASSWORD::"
        },
        {
          "name": "REDIS_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:aideals/production/secrets:REDIS_PASSWORD::"
        },
        {
          "name": "JWT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:aideals/production/secrets:JWT_SECRET::"
        },
        {
          "name": "DEEPSEEK_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:aideals/production/secrets:DEEPSEEK_API_KEY::"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:aideals/production/secrets:OPENAI_API_KEY::"
        }
      ]
    }
  ]
}
```

## Lambda Integration

For Lambda functions, you can access the secrets using the AWS SDK:

```python
import boto3
import json
from botocore.exceptions import ClientError

def get_secret(secret_name):
    region_name = "us-east-1"  # Replace with your region
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            raise ValueError("Secret is binary and not supported")

# Example usage
def lambda_handler(event, context):
    try:
        secrets = get_secret("aideals/production/secrets")
        db_password = secrets['POSTGRES_PASSWORD']
        
        # Use the password to connect to database
        # ...
        
        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
```

## IAM Permissions

The following IAM permissions are required for the ECS task or Lambda function to access the secrets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:aideals/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/aideals/*"
      ]
    }
  ]
}
```

## Health Check Configuration

AWS expects health check endpoints to return HTTP 200 status codes for healthy services. The AI Agentic Deals System provides the following health check endpoints:

### Basic Health Check 

**Endpoint**: `/health`  
**Response Format**:
```json
{
  "status": "healthy",
  "timestamp": "2023-06-01T12:00:00Z",
  "version": "1.0.0"
}
```

### Full Documentation

For comprehensive health check documentation, please refer to [Health Check Implementation](../monitoring/health_checks/implementation.md). 