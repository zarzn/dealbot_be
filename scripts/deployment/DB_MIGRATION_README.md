# Database Migration Process

This document explains the database migration process for the AI Agentic Deals System.

## Automatic Database Creation and Migration

The system is designed to automatically create the required database and run migrations during application startup. This eliminates the need for manual database setup or separate migration tasks.

### How It Works

1. When the container starts, the entrypoint script (`entrypoint.prod.sh`) performs the following steps:
   - Checks if PostgreSQL and Redis are accessible
   - Creates the database if it doesn't exist
   - Runs database migrations using Alembic
   - Creates initial data if needed
   - Starts the application

### Database Creation Logic

The entrypoint script includes the following functionality:

- Connects to the PostgreSQL server using the default `postgres` database
- Checks if the specified database (`$POSTGRES_DB`) exists
- Creates the database if it doesn't exist
- Handles connection failures and reports errors

## Configuration

The database connection is configured using environment variables, which are provided to the container:

- `POSTGRES_HOST`: Hostname/IP of the PostgreSQL server
- `POSTGRES_PORT`: Port of the PostgreSQL server (default: 5432)
- `POSTGRES_USER`: Username for PostgreSQL authentication
- `POSTGRES_PASSWORD`: Password for PostgreSQL authentication
- `POSTGRES_DB`: Name of the database to create/connect to (default: `agentic_deals`)

## Legacy Migration Approach (AWS ECS Task)

Previously, a separate ECS task was used to create the database and run migrations. This approach is still available but no longer required for normal operation:

1. The migration task definition is available at `backend/scripts/deployment/hardcoded-migration-task-definition.json`
2. It can be registered and run using the AWS CLI:

```bash
# Register the task definition
aws ecs register-task-definition --profile agentic-deals-deployment --region us-east-1 --cli-input-json file://backend/scripts/deployment/hardcoded-migration-task-definition.json

# Run the task
aws ecs run-task --profile agentic-deals-deployment --region us-east-1 --cluster agentic-deals-cluster --task-definition agentic-deals-migrations:latest --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[subnet-ids],securityGroups=[sg-ids],assignPublicIp=DISABLED}"
```

## Troubleshooting

### Database Connection Issues

If the application fails to start, check the container logs for database connection errors:

```bash
# View container logs
aws logs get-log-events --profile agentic-deals-deployment --log-group-name /ecs/agentic-deals-service --log-stream-name <log-stream-name>
```

### Common Errors

1. **Database already exists**: This is not an error, the script will proceed with migrations.
2. **Connection refused**: Ensure the database server is accessible from the container network and check security groups.
3. **Authentication failed**: Verify the database credentials in the environment variables.

## Manual Database Creation

If you need to create the database manually, you can connect to the PostgreSQL server and execute:

```sql
CREATE DATABASE agentic_deals;
```

Or using the psql command-line tool:

```bash
psql -h <POSTGRES_HOST> -U <POSTGRES_USER> -p <POSTGRES_PORT> -c "CREATE DATABASE agentic_deals;"
``` 