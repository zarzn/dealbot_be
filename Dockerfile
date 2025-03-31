# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
COPY requirements-llm.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-llm.txt

# Copy the rest of the application
COPY . .

# Make scripts executable
RUN chmod +x scripts/deployment/entrypoint.prod.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the entrypoint script
CMD ["./scripts/deployment/entrypoint.prod.sh", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"] 