# Test Scripts

This directory contains scripts for running tests in the application.

## Scripts

- `run_consolidated_tests.ps1`: PowerShell script to run all tests with proper environment configuration

## Usage

### Run All Tests

```powershell
.\backend\scripts\dev\test\run_consolidated_tests.ps1
```

## Features

- Properly loads `.env.test` for test environment configuration
- Runs tests by category (Core, Service, Feature, Integration)
- Generates HTML reports for each test category
- Creates a summary file with test results
- Handles test failures and provides detailed output

## Notes

- This script is designed to run in a Windows PowerShell environment
- It handles test execution, reporting, and result collection
- Test results are stored in the `backend/backend_tests/test_results` directory
- The script ensures proper environment configuration for testing 