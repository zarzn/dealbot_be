# AI Agentic Deals System Test Scripts

This directory contains scripts for running tests in the AI Agentic Deals System project.

## Available Test Scripts

The test suite is divided into several categories, each with its own script:

1. **run_core_tests.ps1** - Runs only core tests
2. **run_service_tests.ps1** - Runs only service tests
3. **run_feature_tests.ps1** - Runs only feature tests
4. **run_integration_tests.ps1** - Runs only integration tests
5. **run_all_tests.ps1** - Runs all test categories in sequence with dependency checking
6. **run_patched_tests.ps1** - Original script that runs core and service tests only

## How to Run Tests

### Running a Specific Test Category

To run tests for a specific category, use the corresponding script:

```powershell
# Run core tests only
.\run_core_tests.ps1

# Run service tests only
.\run_service_tests.ps1

# Run feature tests only
.\run_feature_tests.ps1

# Run integration tests only
.\run_integration_tests.ps1
```

### Running All Tests

To run all test categories in sequence with dependency checking:

```powershell
.\run_all_tests.ps1
```

This will run the test categories in the following order:
1. Core tests
2. Service tests (if core tests pass)
3. Feature tests (if core and service tests pass)
4. Integration tests (if all previous tests pass)

### Test Results

Test results are saved in the following locations:

- HTML reports: `C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend\scripts\test_results\*_report.html`
- Summary files: `C:\Active Projects\AI AGENTIC DEALS SYSTEM\backend\scripts\test_results\*_test_summary.txt`

## Test Categories and Markers

The test suite uses the following pytest markers:

- `core`: Core functionality tests (run first)
- `service`: Service tests (run second)
- `feature`: Feature tests (run third)
- `integration`: Integration tests (run last)
- `unit`: Unit tests
- `api`: API tests
- `slow`: Slow tests (skipped by default)
- `redis`: Tests that require Redis
- `websocket`: Tests that require WebSocket
- `scraper`: Tests that require scraper functionality
- `agent`: Tests that require agent functionality

## Troubleshooting

If tests are timing out, you can adjust the timeout values in the scripts:
- Individual test timeout: Modify the `--timeout=60` parameter in the Python script
- Overall script timeout: Modify the `$process.WaitForExit(300000)` value (in milliseconds) 