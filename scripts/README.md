# Scripts Directory

This directory contains various scripts for development, testing, and deployment of the AI Agentic Deals System.

## Directory Structure

- **dev/**: Development scripts
  - **db/**: Database-related scripts
    - `setup_db.py`: Consolidated script for database setup (supports both Docker and local environments)
    - `check_db.py`: Script to check database status
    - `check_db_connection.py`: Script to verify database connection
    - `check_tables.py`: Script to list database tables
    - `check_table.py`: Script to check a specific table
    - `check_data.py`: Script to check data in the database
    - `check_enums.py`: Script to verify enum values
    - `check_markets.py`: Script to check market data
    - `init_db.py`: Script to initialize the database
    - `add_unique_constraint.py`: Script to add unique constraints
    - `cleanup_duplicates.py`: Script to clean up duplicate data
    - `add_market_search_pricing.py`: Script to add market search pricing
  - **test/**: Testing scripts
    - `run_consolidated_tests.ps1`: PowerShell script to run all tests with proper environment configuration
  - **debug/**: Debugging scripts
    - `check_pricing.py`: Script to check pricing
    - `api_mount_test_fix.py`: Script to fix API mount tests
    - `test_script.py`: General test script
    - `debug_deals_endpoint.py`: Script to debug deals endpoint
    - `debug_routes.py`: Script to debug API routes
    - `fixed_test_deal_service.py`: Fixed test for deal service

- **deployment/**: Deployment scripts
  - `start.sh`: Script to start the application
  - `entrypoint.prod.sh`: Production entrypoint script

## Usage

### Database Setup

To set up the database using Docker:

```bash
python backend/scripts/dev/db/setup_db.py
```

To set up the database using local connection:

```bash
python backend/scripts/dev/db/setup_db.py --local
```

### Running Tests

To run tests:

```powershell
.\backend\scripts\dev\test\run_consolidated_tests.ps1
```

### Deployment

To deploy the application:

```bash
./backend/scripts/deployment/start.sh
```

## Notes

- All database-related scripts are now consolidated in the `dev/db` directory
- Debug scripts are moved to the `dev/debug` directory
- Test scripts are organized in the `dev/test` directory
- Deployment scripts are in the `deployment` directory 