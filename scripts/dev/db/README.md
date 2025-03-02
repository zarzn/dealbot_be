# Database Scripts

This directory contains scripts for database management and operations.

## Main Scripts

- `setup_db.py`: Consolidated script for database setup (supports both Docker and local environments)
  - Resets the database
  - Initializes the database with required extensions
  - Runs migrations
  - Creates a default user

## Utility Scripts

- `check_db.py`: Script to check database status and perform basic operations
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

### Check Database Connection

```bash
python backend/scripts/dev/db/check_db_connection.py
```

### Check Database Tables

```bash
python backend/scripts/dev/db/check_tables.py
```

## Notes

- The `setup_db.py` script is a consolidated version of `setup_db.py` and `setup_db_local.py`
- It supports both Docker and local environments through the `--local` flag
- All database operations are performed with proper error handling and logging 