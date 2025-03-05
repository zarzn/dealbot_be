#!/bin/sh

set -e

# Change to the application directory
cd /app

# Run the migration script
echo "Starting AWS database migrations..."
python -m scripts.deployment.aws_migrate

# Check the exit code
if [ $? -eq 0 ]; then
    echo "AWS database migrations completed successfully"
    exit 0
else
    echo "AWS database migrations failed"
    exit 1
fi 