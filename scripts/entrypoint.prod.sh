#!/bin/sh

set -e

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.1
done
echo "PostgreSQL started"

# Wait for Redis
echo "Waiting for Redis..."
while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
    sleep 0.1
done
echo "Redis started"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Create initial data if needed
echo "Creating initial data..."
python -m scripts.create_initial_data

# Start the application
echo "Starting application..."
exec "$@" 