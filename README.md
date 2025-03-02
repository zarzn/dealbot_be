# AI Agentic Deals System - Backend

## Environment Configuration

This project uses environment-specific configuration files to manage different deployment environments:

- `.env.development` - For local development
- `.env.production` - For production deployment
- `.env.test` - For testing

### Environment Setup

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

### Docker Compose Configuration

The project includes Docker Compose files for different environments:

- `docker-compose.yml` - For local development
- `docker-compose.prod.yml` - For production deployment

#### Development Environment

To start the development environment:

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (container name: deals_postgres)
- Redis (container name: deals_redis)
- Backend API (container name: deals_backend)

#### Production Environment

To start the production environment:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

This will start:
- PostgreSQL database (container name: deals_postgres_prod)
- Redis with TLS (container name: deals_redis_prod)
- Backend API with replicas (container name: deals_backend_prod)
- Nginx for reverse proxy (container name: deals_nginx_prod)
- Prometheus for monitoring (container name: deals_prometheus)
- Grafana for visualization (container name: deals_grafana)

### Database Configuration

- Development database name: `deals`
- Test database name: `deals_test`
- Production database name: `agentic-deals-db`

### Redis Configuration

- Development Redis host: `deals_redis`
- Test Redis host: `localhost`
- Production Redis host: Configured via environment variables

## Important Notes

1. Never commit sensitive information like API keys or passwords to version control.
2. Always use environment variables for sensitive information.
3. The `.env.example` file provides a template with placeholders for all required variables.
4. In production, ensure all passwords and keys are strong and unique.

## Troubleshooting

If you encounter issues with the environment configuration:

1. Verify that all required environment variables are set.
2. Check container logs for error messages:
   ```bash
   docker-compose logs [service_name]
   ```
3. Ensure that the database and Redis services are running and healthy before starting the API service. 