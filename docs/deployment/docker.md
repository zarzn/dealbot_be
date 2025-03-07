# Docker Configuration

This document describes the Docker configuration for the AI Agentic Deals System.

## Overview

The system uses Docker Compose to manage containerized services for different environments:

- Development environment: `docker-compose.yml`
- Production environment: `docker-compose.prod.yml`

## Docker Compose Files

### docker-compose.yml

Located in the `backend` directory, this file is used for local development and includes:

- PostgreSQL database (container name: deals_postgres)
- Redis (container name: deals_redis)
- Backend API (container name: deals_backend)

```yaml
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    container_name: deals_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-your_redis_password}
    networks:
      - deals_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:15-alpine
    container_name: deals_postgres
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-postgres}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-12345678}
      - POSTGRES_DB=${POSTGRES_DB:-agentic_deals}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - deals_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: deals_backend
    env_file:
      - .env.development
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - deals_network
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### docker-compose.prod.yml

Located in the `backend` directory, this file is used for production deployment and includes:

- PostgreSQL database (container name: deals_postgres_prod)
- Redis with TLS (container name: deals_redis_prod)
- Backend API with replicas (container name: deals_backend_prod)
- Nginx for reverse proxy (container name: deals_nginx_prod)
- Prometheus for monitoring (container name: deals_prometheus)
- Grafana for visualization (container name: deals_grafana)

```yaml
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    container_name: deals_redis_prod
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD} --tls-port 6379 --tls-cert-file /certs/redis.crt --tls-key-file /certs/redis.key --tls-ca-cert-file /certs/ca.crt
    volumes:
      - redis_data:/data
      - ./certs:/certs
    networks:
      - deals_network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:15-alpine
    container_name: deals_postgres_prod
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    networks:
      - deals_network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: deals_backend_prod
    env_file:
      - .env.production
    environment:
      - ENVIRONMENT=production
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - deals_network
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
      restart_policy:
        condition: on-failure
        max_attempts: 3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Environment Configuration

Docker Compose files use environment variables from the following files:

- Development: `.env.development`
- Production: `.env.production`

### Environment Variables in Docker Compose

Docker Compose files use environment variables with default values for non-sensitive configuration:

```yaml
environment:
  - POSTGRES_USER=${POSTGRES_USER:-postgres}
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-12345678}
  - POSTGRES_DB=${POSTGRES_DB:-agentic_deals}
```

This pattern allows for:
- Default values when environment variables are not set
- Overriding values from environment files
- Consistent configuration across environments

## Docker Images

### Backend API

#### Development Image (Dockerfile)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

#### Production Image (Dockerfile.prod)

```dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Deployment Process

### Development Deployment

1. Start the development environment:
   ```bash
   cd backend
   docker-compose up -d
   ```

2. Verify services are running:
   ```bash
   docker-compose ps
   ```

3. Access the API at http://localhost:8000

### Production Deployment

1. Create necessary certificates for Redis TLS:
   ```bash
   mkdir -p certs
   # Generate certificates using your preferred method
   ```

2. Start the production environment:
   ```bash
   cd backend
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. Verify services are running:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

4. Access the API through Nginx at http://your-domain.com

## Scaling

The production configuration includes settings for scaling:

```yaml
deploy:
  replicas: 3
  resources:
    limits:
      cpus: '1'
      memory: 1G
  restart_policy:
    condition: on-failure
    max_attempts: 3
```

To scale services manually:

```bash
docker-compose -f docker-compose.prod.yml up -d --scale backend=5
```

## Monitoring

The production configuration includes Prometheus and Grafana for monitoring:

- Prometheus: Collects metrics from services
- Grafana: Visualizes metrics and provides dashboards

Access Grafana at http://your-domain.com:3000 (default credentials: admin/admin)

## Troubleshooting

### Container Logs

View logs for a specific service:

```bash
docker-compose logs [service_name]
```

For production:

```bash
docker-compose -f docker-compose.prod.yml logs [service_name]
```

### Container Health

Check container health status:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Health}}"
```

### Database Connection Issues

If the backend cannot connect to the database:

1. Verify database container is running:
   ```bash
   docker-compose ps postgres
   ```

2. Check database logs:
   ```bash
   docker-compose logs postgres
   ```

3. Verify environment variables in `.env.development` or `.env.production`

### Redis Connection Issues

If the backend cannot connect to Redis:

1. Verify Redis container is running:
   ```bash
   docker-compose ps redis
   ```