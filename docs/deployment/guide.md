# Deployment Guide for AI Agentic Deals System

This guide provides step-by-step instructions for deploying the AI Agentic Deals System in various environments.

## Prerequisites

Before deploying the system, ensure you have the following:

- Git client
- Docker and Docker Compose
- Access to required API keys:
  - DeepSeek API key (primary)
  - OpenAI API key (fallback)
- PostgreSQL database
- Redis instance
- SSL certificates for production

## Environment Setup

### Environment Variables

The system uses the following environment files:

- `.env.development` - Development environment
- `.env.test` - Testing environment
- `.env.production` - Production environment

Copy the appropriate example file and update it with your configuration:

```bash
# For development
cp .env.example .env.development

# For production
cp .env.example .env.production
```

### Critical Environment Variables

| Variable | Description | Example |
| --- | --- | --- |
| `APP_ENVIRONMENT` | Environment name | `development`, `test`, `production` |
| `DEBUG` | Debug mode | `true` for development, `false` for production |
| `SECRET_KEY` | Security key for JWT | Generate securely, keep private |
| `POSTGRES_HOST` | Database host | `localhost` or `postgres` in Docker |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `deals_production` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | Strong password, keep private |
| `REDIS_HOST` | Redis host | `localhost` or `redis` in Docker |
| `REDIS_PORT` | Redis port | `6379` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | Your API key |
| `OPENAI_API_KEY` | OpenAI API key | Your API key |

## Deployment Options

### 1. Docker Deployment (Recommended)

Docker deployment is the recommended approach for all environments as it ensures consistency across development, testing, and production.

Refer to the [Docker Deployment Guide](docker.md) for detailed instructions.

### 2. Manual Deployment

#### Backend Deployment

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/ai-agentic-deals-system.git
   cd ai-agentic-deals-system
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Linux/Mac
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Set up the environment file:
   ```bash
   cp .env.example .env.production
   # Edit .env.production with your configuration
   ```

5. Initialize the database (first run only):
   ```bash
   cd backend
   python setup_db.py --environment production
   ```

6. Start the backend server:
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

7. Start Celery workers (in a separate terminal):
   ```bash
   cd backend
   celery -A core.celery_app worker --loglevel=info
   ```

8. Start Celery beat (in a separate terminal):
   ```bash
   cd backend
   celery -A core.celery_app beat --loglevel=info
   ```

#### Frontend Deployment

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Build the frontend:
   ```bash
   npm run build
   ```

3. Serve the built files using a web server like Nginx.

## Production Deployment Considerations

### Database Migration

Before deploying a new version in production:

1. Backup the existing database:
   ```bash
   pg_dump -U postgres -F c -b -v -f backup_$(date +%Y%m%d%H%M%S).dump deals_production
   ```

2. Apply migrations carefully, testing first in a staging environment.

### Health Check Configuration

Configure health checks for your production environment:

1. Database health check: `/api/health/database`
2. Redis health check: `/api/health/redis`
3. API health check: `/api/health`

### Performance Optimization

For production deployment, consider the following optimizations:

1. **Database Optimization**:
   - Increase pool size in production (20-30)
   - Set appropriate timeouts
   - Configure PostgreSQL for your server resources

2. **Worker Configuration**:
   - Adjust number of Celery workers based on CPU cores
   - Configure task queues for priority tasks

3. **Caching Configuration**:
   - Enable Redis cache for production
   - Set appropriate TTL for cached items
   - Configure cache invalidation strategies

### High Availability Setup

For mission-critical deployments:

1. Use load balancing with multiple backend instances
2. Set up database replication
3. Configure Redis sentinel or cluster
4. Implement regular backups
5. Set up monitoring and alerting

## Monitoring and Logging

### Logging Configuration

Production logs are configured in `main.py` with the following settings:

- Log level: WARNING (to reduce noise)
- Log rotation: Enabled (10MB file size, 5 backup files)
- Structured logging format for improved analysis

### Monitoring Integration

Configure monitoring for your production deployment:

1. Set up Prometheus metrics at `/metrics`
2. Configure Grafana dashboards for visualization
3. Implement alert policies for critical issues

## Security Considerations

1. Always use HTTPS in production
2. Secure all API endpoints with proper authentication
3. Rotate API keys and credentials regularly
4. Implement rate limiting for API endpoints
5. Use secure headers and CORS configuration
6. Enable database encryption for sensitive data
7. Implement proper error handling to prevent information leakage
8. Configure firewall rules to restrict access

## Deployment Checklist

Before final deployment, verify:

- [ ] All environment variables are correctly set
- [ ] Database migrations have been tested
- [ ] API keys are valid and have appropriate permissions
- [ ] SSL certificates are installed and valid
- [ ] Health checks pass for all components
- [ ] Logging is properly configured
- [ ] Monitoring is set up and functional
- [ ] Backups are configured and tested
- [ ] Security measures are in place
- [ ] Load testing has been performed

## Rollback Procedure

If deployment fails or causes issues:

1. Restore the previous database backup
2. Revert to the previous code version
3. Restart all services
4. Verify system health
5. Investigate the root cause before attempting redeployment

## Support and Troubleshooting

For deployment issues, refer to:

- System logs in `/var/log/deals/`
- Database logs
- Docker logs using `docker logs container_name`
- Application logs in the configured log directory

Contact technical support at: support@example.com

## Maintenance Windows

Schedule regular maintenance during low-usage periods:

- Database maintenance: Weekly (Sunday, 2-4 AM)
- System updates: Monthly (First Sunday, 2-6 AM)
- Security patches: As needed

Notify users at least 48 hours before scheduled maintenance. 