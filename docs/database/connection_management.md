# Database Connection Management

## Overview

This document provides guidelines for properly managing database connections in the AI Agentic Deals System.
Proper connection management is critical to prevent connection leaks, which can exhaust database connections
and lead to application failures.

## Connection Pool Configuration

The system uses SQLAlchemy's connection pooling with the following settings (configured in `core/database.py`):

```python
# Development environment settings
pool_size = 10
max_overflow = 15
pool_timeout = 60
pool_recycle = 300
pool_pre_ping = True
```

## Common Issues

1. **Connection Leaks**: When database sessions aren't properly closed, they remain in the connection pool
   as "checked out" until they're garbage collected. This can eventually exhaust the connection pool.

2. **Garbage Collection Warnings**: If you see warnings like the following, it indicates connections
   aren't being properly managed:

   ```
   The garbage collector is trying to clean up non-checked-in connection <AdaptedConnection>, which will be terminated.
   Please ensure that SQLAlchemy pooled connections are returned to the pool explicitly, either by calling `close()` 
   or by using appropriate context managers to manage their lifecycle.
   ```

## Best Practices

### 1. Always Use Context Managers

The safest way to manage connections is with context managers:

```python
# Preferred pattern - context manager ensures proper cleanup
async with AsyncSession(async_engine) as session:
    # Database operations
    result = await session.execute(query)
    
    # For write operations, explicitly commit
    await session.commit()
    
    # No need to close - context manager handles it
```

### 2. FastAPI Dependency Pattern

For FastAPI endpoints, use the `get_db` dependency:

```python
@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    items = result.scalars().all()
    return items
```

The `get_db` dependency ensures proper cleanup of the session.

### 3. Handle Errors Correctly

When managing sessions manually, ensure proper cleanup in error scenarios:

```python
session = AsyncSessionLocal()
try:
    # Database operations
    await session.commit()
finally:
    await session.close()  # Always close the session
```

### 4. Direct Connection Usage

If you need to use database connections directly (outside of FastAPI dependencies):

```python
async with AsyncDatabaseSession() as session:
    # Use session here
    result = await session.execute(query)
    
    # For write operations
    await session.commit()
```

## Connection Monitoring

The system includes built-in connection monitoring through:

1. **Connection Logging**: Pool usage is logged at regular intervals
2. **Leak Detection**: Long-held connections are detected and logged
3. **Auto Cleanup**: Connections are periodically refreshed to prevent stale connections

## Recent Fixes

### March 2025: Fixed Connection Leak in Public Deals Endpoint

The `public-deals` endpoint in `main.py` was not properly managing database connections.
The issue was fixed by:

1. Adding explicit try/except/finally blocks
2. Ensuring proper commit/rollback of transactions
3. Using AsyncDatabaseSession for safer connection management
4. Adding timing and performance metrics

#### Before Fix:

```python
async with AsyncSession(async_engine) as db:
    # Execute query
    result = await db.execute(stmt)
    deals = result.scalars().all()
    
    # Missing explicit commit/rollback
    return response_deals
```

#### After Fix:

```python
async with AsyncSession(async_engine) as db:
    try:
        # Execute query
        result = await db.execute(stmt)
        deals = result.scalars().all()
        
        # Explicit commit
        await db.commit()
        return response_deals
    except Exception as db_error:
        # Explicit rollback
        await db.rollback()
        logger.error(f"Database error: {str(db_error)}")
        raise
```

## Troubleshooting

If you encounter connection pool issues:

1. Check for proper session management in code
2. Look for non-closed transactions
3. Monitor connection pool status using:
   ```
   SELECT * FROM pg_stat_activity 
   WHERE application_name LIKE 'agentic-deals%';
   ```
4. Use the health endpoint to check database connectivity:
   ```
   GET /api/v1/health
   ``` 