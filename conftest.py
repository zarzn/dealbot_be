"""Configure test environment."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set testing flag
os.environ["TESTING"] = "true"

# Set Redis configuration
os.environ["REDIS_URL"] = "redis://redis:6379/0"
os.environ["REDIS_HOST"] = "redis"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = "your_redis_password"

# Load environment variables from .env.development
env_file = backend_dir / '.env.development'
load_dotenv(env_file) 