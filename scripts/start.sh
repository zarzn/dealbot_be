#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done
echo "PostgreSQL is ready"

# Initialize the database
echo "Initializing database..."
python scripts/init_db.py

# Start the application
echo "Starting application..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload 