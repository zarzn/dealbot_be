# Database Connection Management

## Recent Connection Fixes

We recently addressed a `TooManyConnectionsError` in PostgreSQL by implementing several important optimizations:

### 1. Optimized Pool Settings

In `backend/core/config/settings.py`, we adjusted the following connection pool parameters:

```python
# Previous settings
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 1800
DB_IDLE_TIMEOUT = 300

# New optimized settings
DB_POOL_SIZE = 8
DB_MAX_OVERFLOW = 8
DB_POOL_TIMEOUT = 15
DB_POOL_RECYCLE = 600
DB_IDLE_TIMEOUT = 120
```

These changes balance performance with resource usage:
- Increased `DB_POOL_SIZE` to handle standard load
- Reduced `DB_MAX_OVERFLOW` to prevent excess connections
- Shortened timeouts to recycle connections more frequently

### 2. Improved Connection Management

In the `search_deals` function (`backend/core/services/deal/search/core_search.py`), we:
- Implemented proper database session management with context managers
- Combined the count query and main query using Common Table Expressions (CTEs)
- Added robust error handling with connection cleanup
- Isolated database operations for real-time scraping

### 3. Connection Monitoring Tools

We've created two tools to help diagnose and prevent connection issues:

1. **Automatic Connection Monitor**:
   - Code: `backend/core/utils/connection_monitor.py`
   - Runs as a background task monitoring connection status
   - Closes idle connections automatically
   - Logs warnings when connection usage is high

2. **Diagnostic Scripts**:
   - Container-based diagnostics: `backend/scripts/dev/container_db_diagnostic.py`
   - Provides real-time pool statistics inside the Docker container
   - Detects connection issues directly in the container environment
   - Verifies database connectivity with test queries

## Best Practices for Avoiding Connection Issues

1. **Always use context managers for database sessions**:
   ```python
   # Correct approach
   async with AsyncDatabaseSession() as session:
       result = await session.execute(query)
       # process result
   # connection automatically returned to pool
   ```

2. **Avoid nested transactions without explicit handling**:
   ```python
   # Problematic
   async with AsyncDatabaseSession() as session:
       # ... some code
       async with AsyncDatabaseSession() as inner_session:  # Creates a second connection
           # ... more code
   
   # Better
   async with AsyncDatabaseSession() as session:
       # ... some code
       async with session.begin_nested():  # Uses same connection with savepoint
           # ... more code
   ```

3. **Handle errors properly to ensure connections are closed**:
   ```python
   try:
       async with AsyncDatabaseSession() as session:
           # database operations
   except Exception as e:
       logger.error(f"Database error: {str(e)}")
       # Handle the error appropriately
       raise  # Re-raise if needed
   ```

4. **Avoid global session objects** that might persist between requests

5. **Monitor connection usage** regularly using the diagnostic script

## Diagnosing Connection Issues

### Running Diagnostics in Docker Environment

Since our database runs in a Docker container, you should run the diagnostics inside the container for accurate results:

1. **Using the simplified container diagnostic tool (recommended)**:
   ```powershell
   # From the project root directory
   .\backend\scripts\dev\run_container_db_diagnostic.ps1 -Duration 60 -Interval 5
   ```
   This script:
   - Does not depend on application settings
   - Creates a standalone connection to the database
   - Works even if the application is having configuration issues
   - Provides realtime statistics and test query validation

2. **Using the automated application diagnostic script**:
   ```powershell
   # From the project root directory
   .\backend\scripts\dev\run_db_diagnostics.ps1 -MonitorTime 120 -CheckInterval 10
   ```
   This script uses the application's configuration but might not work if there are settings issues.

3. **Manual diagnostics inside container**:
   ```powershell
   # Find the container ID
   docker ps
   
   # Copy the script to the container
   docker cp backend/scripts/dev/container_db_diagnostic.py CONTAINER_ID:/app/scripts/
   
   # Run inside the container
   docker exec CONTAINER_ID python /app/scripts/container_db_diagnostic.py 60 5
   ```

4. **Local diagnostics (less accurate but useful for development)**:
   ```powershell
   # Make sure your .env has the correct database settings first
   cd backend
   python scripts/dev/diagnose_db_connections.py --monitor-time=120 --check-interval=10
   ```

### Understanding Diagnostic Output

The script will provide:
- Current connection pool statistics
- Analysis of connection usage patterns
- Detection of possible connection leaks
- Recommendations for configuration changes

### Common Issues and Solutions

* **High connection usage**: If consistently using >80% of available connections, increase `DB_POOL_SIZE`
* **Connection leaks**: If connections remain checked out, check for missing context managers or unclosed sessions
* **Connection timeouts**: If seeing timeouts, decrease `DB_POOL_TIMEOUT` to fail faster and `DB_POOL_RECYCLE` to recycle connections more often
* **Erratic connection behavior**: If connection counts fluctuate dramatically, examine high-traffic endpoints and add transaction management

## Connection Limits

PostgreSQL has a default maximum connection limit (typically 100 connections).
With our current settings (pool_size=8, max_overflow=8) and 4 uvicorn workers, the 
theoretical maximum is approximately 64 connections (4 workers × (8+8) connections),
which gives us plenty of headroom under the default PostgreSQL limit. 