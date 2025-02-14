# Run integration tests for price tracking and prediction components

# Set environment variables for testing
$env:TESTING = "True"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_deals_db"
$env:REDIS_URL = "redis://localhost:6379/1"

# Add backend directory to PYTHONPATH
$env:PYTHONPATH = (Get-Location).Path

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
}

# Install test dependencies if needed
pip install pytest pytest-asyncio httpx

# Run the tests with coverage
pytest tests/test_price_integration.py -v --asyncio-mode=auto --cov=core --cov-report=term-missing 