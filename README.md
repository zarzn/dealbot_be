# RebatOn - Backend

This repository contains the backend component of the RebatOn platform, a system for scraping, analyzing, and presenting deal opportunities using AI capabilities.

## Documentation

Comprehensive documentation for the backend is available in the `docs` folder:

- [Architecture](./docs/architecture/architecture.md) - System architecture and design principles
- [Deployment](./docs/deployment/guide.md) - General deployment guide
  - [AWS Deployment](./docs/deployment/aws_deployment.md) - AWS-specific deployment instructions
  - [Docker Deployment](./docs/deployment/docker.md) - Docker-based deployment
  - [Frontend Deployment](./docs/deployment/frontend_deployment.md) - Frontend deployment guide
  - [API Gateway Testing & Logging](./docs/deployment/api_gateway_testing_logging.md) - Testing API integrations and setting up CloudWatch logs
- [Testing](./docs/testing/testing_guide.md) - Comprehensive testing documentation and best practices
- [API Reference](./docs/api/readme.md) - API documentation
  - [REST API](./docs/api/rest_api/README.md) - REST API documentation
  - [WebSocket API](./docs/api/websocket_api/README.md) - WebSocket API documentation

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- API keys for DeepSeek and OpenAI (optional)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rebaton.git
   cd rebaton
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp backend/.env.example backend/.env
   # Edit the .env file with your configuration
   ```

5. Initialize the database:
   ```bash
   python backend/scripts/setup_db.py
   ```

### Running the Server

Start the backend server:

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at http://localhost:8000.

### Running Tests

Run the test suite:

```bash
# Windows PowerShell
.\backend\scripts\dev\test\run_patched_tests.ps1

# Alternative
cd backend
pytest
```

### Testing API Gateway Integrations

Test the API Gateway integrations:

```bash
# REST API Testing
.\backend\scripts\test_api_gateway.ps1 -ApiUrl "https://your-api-id.execute-api.region.amazonaws.com/stage"

# WebSocket API Testing
.\backend\scripts\test_websocket_api.ps1 -WebSocketUrl "wss://your-ws-api-id.execute-api.region.amazonaws.com/stage"

# End-to-End Testing
.\backend\scripts\test_e2e.ps1
```

## LLM Configuration

The system supports multiple LLM providers with the following configuration:

1. **Production Environment**:
   - Primary Model: DeepSeek R1
   - API Key: DEEPSEEK_API_KEY
   - Use Case: Main production model

2. **Fallback Configuration**:
   - Model: GPT-4
   - API Key: OPENAI_API_KEY
   - Use Case: Backup when primary model fails

3. **Test Environment**:
   - Model: Mock LLM
   - No API Key required
   - Use Case: Unit tests and CI/CD

## Real-time Communication

The system supports real-time updates using WebSockets. This enables:
- Live deal updates
- Notifications
- Chat functionality

For detailed information on implementing WebSocket clients and servers, see the [WebSocket API documentation](./docs/api/websocket_api/README.md).

## License

This project is licensed under the MIT License - see the LICENSE file for details.