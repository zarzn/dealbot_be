# Redis Mock Fixes for Task Service Tests

## Issue Summary

Several tests for the Task Service were failing because the Redis mock implementation did not properly support key scanning and task pattern matching. The `scan` method in the Redis mock wasn't correctly returning task keys, which caused task listing and cleanup operations to fail in tests.

## Changes Made

1. Fixed the `scan` method in `RedisMock` class:
   - Implemented proper pattern matching using `fnmatch`
   - Added support for wildcard matching in Redis key patterns
   - Ensured cursor-based pagination works correctly for large result sets

2. Updated mock Redis key data initialization:
   - Added automatic generation of mock task data for testing
   - Ensured task keys follow the expected format (`task:{id}`)
   - Populated with realistic task metadata including timestamps

3. Fixed class naming inconsistencies:
   - Renamed `PipelineMock` to `RedisPipelineMock` to match return types
   - Updated type hints for better code consistency

4. Fixed return type of `expire` method to match Redis behavior:
   - Changed return type from `bool` to `int` (1 for success, 0 for failure)
   - Simplified the implementation by removing duplicate code

## Root Cause Analysis

The issue occurred because the Redis mock implementation was incomplete and didn't properly handle the Redis `scan` command patterns used by the Task Service. When the Task Service attempted to list tasks using a pattern like `task:*`, the mock implementation would return an empty list, causing tests to fail.

Task-related tests require the ability to scan Redis for keys matching specific patterns, which wasn't properly implemented in the mock. Additionally, the class naming and return types were inconsistent, leading to type errors in type-checked environments.

## Implementation Details

The new implementation:
1. Properly handles pattern matching using Python's `fnmatch` module
2. Pre-populates the Redis mock with sample task data for tests
3. Ensures consistent behavior between the mock and real Redis implementations
4. Fixes return type inconsistencies to match real Redis behavior

## Verification

The changes enable the Task Service tests to correctly:
1. List active tasks using pattern matching
2. Clean up completed or expired tasks
3. Manage task metadata through the Redis interface

This ensures that both the task listing and cleanup functionality can be properly tested without requiring a real Redis instance. 