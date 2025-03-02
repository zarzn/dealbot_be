# Deployment Guide

This guide provides instructions for deploying the AI Agentic Deals System in different environments.

## Deployment Environments

The system supports three deployment environments:

1. **Development** - For local development and testing
2. **Testing** - For automated tests and CI/CD pipelines
3. **Production** - For live deployment

## Prerequisites

- Docker and Docker Compose
- Git
- Access to required API keys
- SSL certificates for production

## Environment Configuration

### Environment Files

Each environment uses a specific environment file:

- Development: `.env.development`
- Testing: `.env.test`
- Production: `.env.production`

All environment files follow the structure defined in `.env.example`.

### Setting Up Environment Files

1. Copy the example environment file:
   ```bash
   # For development
   cp .env.example .env.development
   
   # For production
   cp .env.example .env.production
   
   # For testing
   cp .env.example .env.test
   ```

2. Update the values in each environment file according to the environment requirements.

### Critical Environment Variables

#### Database Configuration
```
POSTGRES_USER="postgres"                # PostgreSQL username
POSTGRES_PASSWORD="your_password"       # PostgreSQL password
POSTGRES_DB="deals"                     # PostgreSQL database name
POSTGRES_HOST="deals_postgres"          # PostgreSQL host
```

#### Redis Configuration
```
REDIS_HOST="deals_redis"                # Redis host
REDIS_PORT="6379"                       # Redis port
REDIS_PASSWORD="your_redis_password"    # Redis password
REDIS_SSL="false"                       # Set to true for SSL connection
```

#### Security Configuration
```
SECRET_KEY="your_secret_key"            # Application secret key
JWT_SECRET="your_jwt_secret"            # JWT token secret
```

#### API Keys
```
DEEPSEEK_API_KEY="your_deepseek_key"    # DeepSeek API key
OPENAI_API_KEY="your_openai_key"        # OpenAI API key
```

## Docker Deployment

### Development Deployment

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Start the development environment:
   ```bash
   docker-compose up -d
   ```

3. Verify services are running:
   ```bash
   docker-compose ps
   ```

4. Access the API at http://localhost:8000

### Production Deployment

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create necessary directories:
   ```bash
   mkdir -p certs
   mkdir -p init-scripts
   ```

3. Set up SSL certificates for Redis:
   ```bash
   # Copy your SSL certificates to the certs directory
   cp /path/to/your/certificates/* certs/
   ```

4. Start the production environment:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

5. Verify services are running:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

6. Access the API through Nginx at your domain

## Database Migration

After deploying the application, run database migrations:

```bash
# Inside the backend container
docker-compose exec backend alembic upgrade head

# For production
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Scaling

The production configuration supports scaling:

```bash
# Scale backend service to 5 instances
docker-compose -f docker-compose.prod.yml up -d --scale backend=5
```

## Monitoring

The production deployment includes monitoring tools:

- **Prometheus**: Collects metrics from services
- **Grafana**: Visualizes metrics and provides dashboards

Access Grafana at http://your-domain.com:3000 (default credentials: admin/admin)

## Backup and Restore

### Database Backup

```bash
# Development
docker-compose exec postgres pg_dump -U postgres deals > backup.sql

# Production
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > backup.sql
```

### Database Restore

```bash
# Development
cat backup.sql | docker-compose exec -T postgres psql -U postgres deals

# Production
cat backup.sql | docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${POSTGRES_USER} ${POSTGRES_DB}
```

## Logging

View logs for services:

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend

# Production
docker-compose -f docker-compose.prod.yml logs backend
```

## Troubleshooting

### Common Issues

#### Database Connection Issues
1. Verify database container is running
2. Check database logs
3. Verify environment variables in the appropriate .env file

#### Redis Connection Issues
1. Verify Redis container is running
2. Check Redis logs
3. Verify environment variables in the appropriate .env file

#### API Key Issues
1. Verify API keys are correctly set in the environment file
2. Check API service status
3. Verify API key permissions and quotas

## Security Considerations

1. Use strong, unique passwords for all services
2. Regularly rotate secrets and API keys
3. Use SSL/TLS for all connections in production
4. Implement proper access controls
5. Regularly update all containers and dependencies
6. Monitor for suspicious activities

## Maintenance

### Regular Updates
1. Pull latest code changes
2. Update dependencies
3. Rebuild and restart containers
4. Run database migrations

### Health Checks
1. Monitor service health
2. Check resource usage
3. Verify API endpoints
4. Test critical functionality

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Nginx Documentation](https://nginx.org/en/docs/) 