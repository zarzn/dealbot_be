#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
RETRIES=30
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
  echo "Waiting for PostgreSQL to be ready, $((RETRIES--)) remaining attempts..."
  sleep 1
done

if [ $RETRIES -eq 0 ]; then
  echo "PostgreSQL failed to become ready in time, but continuing anyway..."
else
  echo "PostgreSQL is ready"
fi

# Initialize the database
echo "Initializing database..."
python scripts/init_db.py

# Start the application
echo "Starting application..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload 