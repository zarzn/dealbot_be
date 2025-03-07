# Environment Configuration

This document describes the environment configuration setup for the AI Agentic Deals System.

## Overview

The system uses environment-specific configuration files to manage different deployment environments:

- `.env.development` - For local development
- `.env.production` - For production deployment
- `.env.test` - For testing

All environment files follow a standardized structure defined in `.env.example`.

## Environment Files

### .env.example

This is a template file containing all possible configuration variables with descriptions. Use this file as a reference when creating environment-specific files.

### .env.development

Contains configuration for local development environment:
- Database name: `agentic_deals`
- Database host: `deals_postgres` (Docker container name)
- Redis host: `deals_redis` (Docker container name)
- Debug mode: enabled
- Mock API keys for development

### .env.production

Contains configuration for production deployment:
- Production database credentials
- SSL-enabled Redis configuration
- Real API keys for external services
- Enhanced security settings
- Monitoring configuration

### .env.test

Contains configuration for testing environment:
- Database name: `agentic_deals_test`
- Database host: `localhost`
- Redis host: `localhost`
- Debug mode: enabled
- Mock API keys for testing

## Environment Variables Categories

### Application Configuration
```
PROJECT_NAME="AI Agentic Deals System"  # Name of the application
VERSION="1.0.0"                         # Application version
DEBUG=false                             # Set to true for development environment
ENVIRONMENT="development"               # Options: development, production, test
```

### Security Configuration
```
SECRET_KEY=""                           # Application secret key for general encryption
NEXTAUTH_SECRET=""                      # Secret for NextAuth authentication
JWT_SECRET=""                           # Secret for JWT token generation
JWT_ALGORITHM="HS256"                   # Algorithm used for JWT
ACCESS_TOKEN_EXPIRE_MINUTES="30"        # Access token expiration time in minutes
REFRESH_TOKEN_EXPIRE_DAYS="7"           # Refresh token expiration time in days
```

### Database Configuration
```
POSTGRES_USER=""                        # PostgreSQL username
POSTGRES_PASSWORD=""                    # PostgreSQL password
POSTGRES_DB=""                          # PostgreSQL database name
POSTGRES_HOST=""                        # PostgreSQL host
POSTGRES_PORT="5432"                    # PostgreSQL port
```

### Redis Configuration
```
REDIS_URL=""                            # Redis connection URL
REDIS_HOST=""                           # Redis host
REDIS_PORT="6379"                       # Redis port
REDIS_DB="0"                            # Redis database number
REDIS_PASSWORD=""                       # Redis password
REDIS_SSL="false"                       # Set to true for SSL connection
```

### Token System Configuration
```
ETH_NETWORK_RPC=""                      # Ethereum network RPC URL
SOL_NETWORK_RPC=""                      # Solana network RPC URL
SOL_NETWORK=""                          # Solana network (mainnet, devnet, testnet)
TOKEN_CONTRACT_ADDRESS=""               # Token contract address
TOKEN_REQUIRED_BALANCE=""               # Minimum token balance required
TOKEN_SEARCH_COST=""                    # Cost per search in tokens
```

### Market APIs Configuration
```
AMAZON_ACCESS_KEY=""                    # Amazon API access key
AMAZON_SECRET_KEY=""                    # Amazon API secret key
AMAZON_PARTNER_TAG=""                   # Amazon partner tag
AMAZON_COUNTRY="US"                     # Amazon country code

WALMART_CLIENT_ID=""                    # Walmart API client ID
WALMART_CLIENT_SECRET=""                # Walmart API client secret
```

### AI Services Configuration
```
DEEPSEEK_API_KEY=""                     # DeepSeek API key
OPENAI_API_KEY=""                       # OpenAI API key
GOOGLE_API_KEY=""                       # Google API key
```

## Docker Compose Configuration

The project includes Docker Compose files for different environments:

### docker-compose.yml

Used for local development:
- PostgreSQL database (container name: deals_postgres)
- Redis (container name: deals_redis)
- Backend API (container name: deals_backend)

Example usage:
```bash
docker-compose up -d
```

### docker-compose.prod.yml

Used for production deployment:
- PostgreSQL database (container name: deals_postgres_prod)
- Redis with TLS (container name: deals_redis_prod)
- Backend API with replicas (container name: deals_backend_prod)
- Nginx for reverse proxy (container name: deals_nginx_prod)
- Prometheus for monitoring (container name: deals_prometheus)
- Grafana for visualization (container name: deals_grafana)

Example usage:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Environment Setup Process

1. Copy `.env.example` to create your environment-specific file:
   ```bash
   # For development
   cp .env.example .env.development
   
   # For production
   cp .env.example .env.production
   
   # For testing
   cp .env.example .env.test
   ```

2. Update the values in your environment file according to your needs.

3. When using Docker Compose, the appropriate environment file will be loaded based on the configuration.

## Best Practices

1. Never commit sensitive information like API keys or passwords to version control.
2. Use environment variables for all configuration values.
3. Keep environment files consistent across environments.
4. Document all environment variables in `.env.example`.
5. Use strong, unique passwords and keys in production.
6. Regularly rotate secrets and API keys.
7. Use default values in Docker Compose for non-sensitive configuration.
8. Validate environment variables at application startup.

## Troubleshooting

### Missing Environment Variables
If the application fails to start due to missing environment variables:
1. Check that the appropriate environment file exists.
2. Verify that all required variables are defined.
3. Ensure the environment file is being loaded correctly.

### Database Connection Issues
If the application cannot connect to the database:
1. Verify database host and credentials in the environment file.
2. Check that the database service is running.
3. Ensure network connectivity between the application and database.

### Redis Connection Issues
If the application cannot connect to Redis:
1. Verify Redis host and credentials in the environment file.
2. Check that the Redis service is running.
3. Ensure network connectivity between the application and Redis.

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Environment Variables](https://fastapi.tiangolo.com/advanced/settings/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation) 