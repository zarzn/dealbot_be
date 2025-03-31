# Deployment Process Documentation

## Overview

This document outlines the database initialization and deployment process for the AI Agentic Deals System. It clarifies the role of each script and the correct execution order to ensure proper system initialization.

## Script Roles and Execution Order

### 1. `scripts/deployment/create_db.py`
- **Purpose**: Creates or resets the PostgreSQL database based on the RESET_DB environment variable
- **When to Run**: First in the initialization process
- **Inputs**: Environment variables (POSTGRES_HOST, POSTGRES_USER, etc.) and RESET_DB flag
- **Outputs**: A fresh or existing database ready for migrations

### 2. Alembic Migrations (`alembic upgrade head`)
- **Purpose**: Apply database schema migrations 
- **When to Run**: After database creation/reset
- **Inputs**: Alembic migration files
- **Outputs**: Database schema with all tables and relationships defined

### 3. `scripts/init_db.py`
- **Purpose**: Create database extensions and ensure tables exist
- **When to Run**: After migrations
- **Inputs**: Environment variables for database connection
- **Outputs**: Fully initialized database with extensions

### 4. `scripts/create_initial_data.py`
- **Purpose**: Populate the database with initial data (users, markets, etc.)
- **When to Run**: After database initialization
- **Inputs**: Database session
- **Outputs**: Database with initial data ready for application use

## Entry Point Scripts

### `scripts/deployment/entrypoint.prod.sh`
- **Purpose**: Main entry point for the Docker container
- **Process**:
  1. Waits for PostgreSQL and Redis to be ready
  2. Calls `create_db.py` to create/reset the database
  3. Runs Alembic migrations
  4. Calls `init_db.py` to initialize database extensions
  5. Calls `create_initial_data.py` to populate initial data
  6. Starts the application

## Redundant Scripts (Not Used)

### `scripts/deployment/start.sh`
- **Status**: Deprecated, replaced by `entrypoint.prod.sh`
- **Note**: Do not use this script for new deployments

### `scripts/deployment/aws_migrate.py`
- **Status**: Redundant, functionality incorporated into `entrypoint.prod.sh`
- **Note**: The functionality is now split across multiple specialized scripts

## Environment Variables

- **RESET_DB**: Set to "true" to reset the database on startup
- **POSTGRES_HOST**: Database hostname
- **POSTGRES_PORT**: Database port
- **POSTGRES_USER**: Database username
- **POSTGRES_PASSWORD**: Database password
- **POSTGRES_DB**: Database name
- **REDIS_HOST**: Redis hostname
- **REDIS_PORT**: Redis port
- **USE_PARAMETER_STORE**: Whether to use AWS Parameter Store for configuration

## AWS Deployment

For AWS ECS deployment, the task definition should include:

1. All required environment variables or references to Parameter Store
2. Health check configuration pointing to `/health` endpoint
3. Proper volume mounts if needed
4. Task and execution IAM roles with appropriate permissions

## Troubleshooting

### Database Reset Issues
- Check if `RESET_DB` parameter is correctly set in Parameter Store
- Check logs for any errors during database reset process
- Verify permissions for database user

### Migration Issues
- Check Alembic migration files for errors
- Verify database connectivity
- Check logs for specific SQL errors

### Initial Data Issues
- Verify database session creation
- Check for conflicts with existing data
- Review logs for transaction errors 