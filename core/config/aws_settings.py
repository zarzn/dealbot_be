"""AWS Settings Helper.

This module provides utilities for loading settings from AWS Parameter Store
and Secrets Manager when running in an AWS environment.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Check if we're running in an AWS environment
IS_AWS_ENVIRONMENT = os.environ.get("AWS_EXECUTION_ENV") is not None or \
                     os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None or \
                     os.environ.get("ECS_CONTAINER_METADATA_URI") is not None

# Flag to control whether Parameter Store should be used
USE_PARAMETER_STORE = os.environ.get("USE_PARAMETER_STORE", "false").lower() in ("true", "1", "yes")

# Flag to control whether Secrets Manager should be used
USE_SECRETS_MANAGER = os.environ.get("USE_SECRETS_MANAGER", "false").lower() in ("true", "1", "yes")

def is_aws_environment() -> bool:
    """Check if the application is running in an AWS environment.
    
    Returns:
        bool: True if running in AWS, False otherwise
    """
    return IS_AWS_ENVIRONMENT

def load_aws_parameters() -> Dict[str, str]:
    """Load parameters from AWS Parameter Store.
    
    This function attempts to load parameters from AWS Parameter Store
    when running in an AWS environment. It requires the boto3 library
    and appropriate IAM permissions.
    
    Returns:
        Dict[str, str]: Dictionary of parameters
    """
    if not is_aws_environment() or not USE_PARAMETER_STORE:
        logger.debug("Not running in AWS environment or Parameter Store disabled, skipping Parameter Store loading")
        return {}
    
    # Quick fail if boto3 is not available
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, cannot load from AWS Parameter Store")
        return {}
    
    try:
        # Create standard boto3 client
        logger.info("Loading parameters from AWS Parameter Store")
        ssm = boto3.client('ssm')
        
        # Fetch parameters with /aideals/production/ prefix
        response = ssm.get_parameters_by_path(
            Path='/aideals/production/',
            Recursive=True,
            WithDecryption=True
        )
        
        parameters = {}
        for param in response.get('Parameters', []):
            # Extract the parameter name without the prefix
            name = param['Name'].split('/')[-1].upper()
            parameters[name] = param['Value']
            
        # Continue pagination if needed
        while 'NextToken' in response:
            response = ssm.get_parameters_by_path(
                Path='/aideals/production/',
                Recursive=True,
                WithDecryption=True,
                NextToken=response['NextToken']
            )
            for param in response.get('Parameters', []):
                name = param['Name'].split('/')[-1].upper()
                parameters[name] = param['Value']
        
        logger.info(f"Loaded {len(parameters)} parameters from Parameter Store")
        return parameters
    except Exception as e:
        logger.error(f"Error loading parameters from AWS Parameter Store: {str(e)}")
        return {}

def load_aws_secrets() -> Dict[str, str]:
    """Load secrets from AWS Secrets Manager.
    
    This function attempts to load secrets from AWS Secrets Manager
    when running in an AWS environment. It requires the boto3 library
    and appropriate IAM permissions.
    
    Returns:
        Dict[str, str]: Dictionary of secrets
    """
    if not is_aws_environment() or not USE_SECRETS_MANAGER:
        logger.debug("Not running in AWS environment or Secrets Manager disabled, skipping Secrets Manager loading")
        return {}
    
    # Quick fail if boto3 is not available
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, cannot load from AWS Secrets Manager")
        return {}
    
    try:
        # Create standard boto3 client without custom configs
        logger.info("Loading secrets from AWS Secrets Manager")
        secrets_manager = boto3.client('secretsmanager')
        
        secrets = {}
        
        # Try database credentials secret
        try:
            db_secret_name = "agentic-deals/database-MiX8h4"
            logger.info(f"Attempting to get database secret: {db_secret_name}")
            db_response = secrets_manager.get_secret_value(SecretId=db_secret_name)
            if 'SecretString' in db_response:
                db_secret_data = json.loads(db_response['SecretString'])
                # Map to appropriate environment variable names
                if 'host' in db_secret_data:
                    secrets['POSTGRES_HOST'] = db_secret_data['host']
                elif 'POSTGRES_HOST' in db_secret_data:
                    secrets['POSTGRES_HOST'] = db_secret_data['POSTGRES_HOST']
                
                if 'port' in db_secret_data:
                    secrets['POSTGRES_PORT'] = str(db_secret_data['port'])
                elif 'POSTGRES_PORT' in db_secret_data:
                    secrets['POSTGRES_PORT'] = str(db_secret_data['POSTGRES_PORT'])
                
                if 'username' in db_secret_data:
                    secrets['POSTGRES_USER'] = db_secret_data['username']
                elif 'POSTGRES_USER' in db_secret_data:
                    secrets['POSTGRES_USER'] = db_secret_data['POSTGRES_USER']
                
                if 'password' in db_secret_data:
                    secrets['POSTGRES_PASSWORD'] = db_secret_data['password']
                elif 'POSTGRES_PASSWORD' in db_secret_data:
                    secrets['POSTGRES_PASSWORD'] = db_secret_data['POSTGRES_PASSWORD']
        except Exception as e:
            logger.error(f"Error accessing database secret: {str(e)}")
        
        # Try Redis cache credentials secret
        try:
            redis_secret_name = "agentic-deals-cache-credentials-f9uaQo"
            logger.info(f"Attempting to get Redis secret: {redis_secret_name}")
            redis_response = secrets_manager.get_secret_value(SecretId=redis_secret_name)
            if 'SecretString' in redis_response:
                redis_secret_data = json.loads(redis_response['SecretString'])
                if 'REDIS_HOST' in redis_secret_data:
                    secrets['REDIS_HOST'] = redis_secret_data['REDIS_HOST']
                elif 'host' in redis_secret_data:
                    secrets['REDIS_HOST'] = redis_secret_data['host']
                
                if 'REDIS_PORT' in redis_secret_data:
                    secrets['REDIS_PORT'] = str(redis_secret_data['REDIS_PORT'])
                elif 'port' in redis_secret_data:
                    secrets['REDIS_PORT'] = str(redis_secret_data['port'])
                
                if 'REDIS_PASSWORD' in redis_secret_data:
                    secrets['REDIS_PASSWORD'] = redis_secret_data['REDIS_PASSWORD']
                elif 'password' in redis_secret_data:
                    secrets['REDIS_PASSWORD'] = redis_secret_data['password']
        except Exception as e:
            logger.error(f"Error accessing Redis secret: {str(e)}")
        
        # Return merged secrets
        logger.info(f"Successfully loaded {len(secrets)} secrets from AWS Secrets Manager")
        return secrets
            
    except Exception as e:
        logger.error(f"Error loading secrets from AWS Secrets Manager: {str(e)}")
        return {}

def load_aws_environment_variables() -> None:
    """Load environment variables from AWS Parameter Store and Secrets Manager.
    
    This function loads parameters and secrets from AWS services and sets them
    as environment variables. It should be called at application startup before
    loading the main settings.
    """
    if not is_aws_environment():
        logger.debug("Not running in AWS environment, skipping AWS environment variables loading")
        return
    
    logger.info(f"Current AWS services configuration: USE_PARAMETER_STORE={USE_PARAMETER_STORE}, USE_SECRETS_MANAGER={USE_SECRETS_MANAGER}")
    
    # Only load from AWS services if explicitly enabled
    if USE_PARAMETER_STORE:
        logger.info("Loading parameters from Parameter Store...")
        parameters = load_aws_parameters()
        for key, value in parameters.items():
            if key not in os.environ:
                os.environ[key] = value
        logger.info(f"Loaded {len(parameters)} environment variables from AWS Parameter Store")
    else:
        logger.info("Parameter Store loading is disabled, skipping")
    
    if USE_SECRETS_MANAGER:
        logger.info("Loading secrets from Secrets Manager...")
        secrets = load_aws_secrets()
        for key, value in secrets.items():
            if key not in os.environ:
                os.environ[key] = str(value)
        logger.info(f"Loaded {len(secrets)} environment variables from AWS Secrets Manager")
    else:
        logger.info("Secrets Manager loading is disabled, skipping")
    
    logger.info("AWS environment variables loading completed")

def get_aws_parameter(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get a parameter value from AWS Parameter Store.
    
    This is a utility function that can be used to get individual parameters
    from Parameter Store without loading all parameters.
    
    Args:
        name: Parameter name to get
        default: Default value if parameter doesn't exist
        
    Returns:
        Parameter value or default if not found
    """
    if not is_aws_environment() or not USE_PARAMETER_STORE:
        return default
    
    try:
        import boto3
        ssm = boto3.client('ssm')
        
        # Build the full parameter name
        app_env = os.environ.get("APP_ENVIRONMENT", "development").lower()
        param_name = f"/aideals/{app_env}/{name}"
        
        response = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        logger.warning(f"Could not get parameter {name}: {str(e)}")
        return default 