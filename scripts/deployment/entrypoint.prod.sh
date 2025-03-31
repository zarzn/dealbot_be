#!/bin/sh

set -e

# Function to check if a port is open
check_port() {
    host=$1
    port=$2
    
    # Try netcat-openbsd first
    if command -v nc > /dev/null 2>&1; then
        nc -z "$host" "$port"
        return $?
    # Try netcat-traditional as fallback
    elif command -v netcat > /dev/null 2>&1; then
        netcat -z "$host" "$port"
        return $?
    # If neither is available, use timeout and bash
    else
        (echo > /dev/tcp/$host/$port) >/dev/null 2>&1
        return $?
    fi
}

# Function to create or reset database
create_or_reset_database() {
    echo "Database management: Checking database status..."
    
    # Make sure psycopg2-binary is installed
    pip install psycopg2-binary
    
    # Execute the create_db.py script (handles create or reset)
    echo "Running database creation/reset script..."
    python -m scripts.deployment.create_db
    
    # Check the exit status
    if [ $? -ne 0 ]; then
        echo "Failed to create or reset database, aborting."
        return 1
    fi
    
    return 0
}

# Wait for PostgreSQL
echo "Waiting for PostgreSQL to be ready..."
while ! check_port "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.1
done
echo "PostgreSQL is ready"

# Create or reset database as needed
echo "Initializing database..."
if ! create_or_reset_database; then
    echo "Database initialization failed. Exiting."
    exit 1
fi

# Wait for Redis
echo "Waiting for Redis..."
while ! check_port "$REDIS_HOST" "$REDIS_PORT"; do
    sleep 0.1
done
echo "Redis started"

# Run migrations using Alembic
echo "Running database migrations..."
alembic upgrade head
if [ $? -ne 0 ]; then
    echo "Database migration failed. Exiting."
    exit 1
fi
echo "Database migrations completed successfully"

# Initialize database tables and extensions
echo "Initializing database tables and extensions..."
python -m scripts.init_db
if [ $? -ne 0 ]; then
    echo "Database table initialization failed. Exiting."
    exit 1
fi
echo "Database tables and extensions initialized successfully"

# Create initial data
echo "Creating initial data..."
cd /app
echo "Current directory: $(pwd)"
echo "Initializing admin users and system data..."
# Run with more detailed logging to diagnose any issues
python -m scripts.create_initial_data
if [ $? -ne 0 ]; then
    echo "ERROR: Initial data creation failed! Check the logs for details."
    echo "WARNING: Continuing with application startup despite initial data creation failure."
else
    echo "Initial data creation completed successfully."
fi

# Start the application
echo "Starting application..."
exec "$@" 