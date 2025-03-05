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

# Function to create database if it doesn't exist
create_database_if_not_exists() {
    echo "Checking if database '$POSTGRES_DB' exists..."
    
    # Make sure psycopg2-binary is installed
    pip install psycopg2-binary
    
    # Create a Python script to check and create database
    cat > /tmp/create_db.py << 'EOF'
import os
import sys
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Get database connection parameters from environment
db_host = os.environ.get('POSTGRES_HOST')
db_port = os.environ.get('POSTGRES_PORT', '5432')
db_user = os.environ.get('POSTGRES_USER')
db_password = os.environ.get('POSTGRES_PASSWORD')
db_name = os.environ.get('POSTGRES_DB', 'agentic_deals')

print(f"Checking if database '{db_name}' exists...")

try:
    # Connect to postgres database
    print(f"Connecting to postgres database at {db_host}:{db_port} as {db_user}")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if the database exists
    cursor.execute(sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), (db_name,))
    exists = cursor.fetchone()
    
    if exists:
        print(f"Database '{db_name}' already exists.")
    else:
        print(f"Creating database '{db_name}'...")
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        print(f"Database '{db_name}' created successfully.")
    
    cursor.close()
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"Failed to create database: {str(e)}")
    sys.exit(1)
EOF

    # Execute the Python script
    python /tmp/create_db.py
    
    # Check the exit status
    if [ $? -ne 0 ]; then
        echo "Failed to create database, aborting."
        return 1
    fi
    
    return 0
}

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
while ! check_port "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.1
done
echo "PostgreSQL started"

# Create database if it doesn't exist
echo "Checking and creating database if needed..."
if ! create_database_if_not_exists; then
    echo "Database preparation failed. Exiting."
    exit 1
fi

# Wait for Redis
echo "Waiting for Redis..."
while ! check_port "$REDIS_HOST" "$REDIS_PORT"; do
    sleep 0.1
done
echo "Redis started"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Create initial data if needed
echo "Creating initial data..."
cd /app
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la
echo "Running create_initial_data script..."
python -m scripts.create_initial_data || echo "Warning: Initial data creation failed, but continuing with application startup."

# Start the application
echo "Starting application..."
exec "$@" 