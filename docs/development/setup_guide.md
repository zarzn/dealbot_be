# Development Setup Guide

## Prerequisites

### Required Software
- Python 3.11+
- Node.js 18+
- Docker Desktop
- PostgreSQL 15+
- Redis 7+
- Git

### Development Tools
- Visual Studio Code or PyCharm
- Docker Compose
- PowerShell (Windows)

## Environment Setup

### 1. Clone the Repository
```powershell
git clone https://github.com/your-org/ai-agentic-deals-system.git
cd ai-agentic-deals-system
```

### 2. Backend Setup

#### Create Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

#### Install Dependencies
```powershell
cd backend
pip install -r requirements.txt
```

#### Environment Configuration
1. Copy environment template:
```powershell
Copy-Item .env.development .env
```

2. Configure environment variables in `.env`:
```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@deals_postgres:5432/deals
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=deals
POSTGRES_HOST=deals_postgres
POSTGRES_PORT=5432

# Redis Configuration
REDIS_URL=redis://deals_redis:6379/0

# API Keys
WALMART_API_KEY=your_walmart_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# JWT Configuration
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key

# Blockchain Configuration
SOL_NETWORK_RPC=your_solana_rpc_url
TOKEN_CONTRACT_ADDRESS=your_token_contract_address
TOKEN_REQUIRED_BALANCE=1.0
TOKEN_SEARCH_COST=0.1

# Agent Configuration
AGENT_MEMORY_LIMIT=512MB
AGENT_TIMEOUT=30
AGENT_MAX_RETRIES=3
AGENT_BATCH_SIZE=100
AGENT_QUEUE_PREFIX=agent
```

### 3. Frontend Setup

#### Install Dependencies
```powershell
cd frontend
npm install
```

#### Environment Configuration
1. Copy environment template:
```powershell
Copy-Item .env.example .env.local
```

2. Configure environment variables in `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/notifications/ws
```

### 4. Docker Setup

#### Start Development Environment
```powershell
docker-compose up -d
```

This will start:
- PostgreSQL database
- Redis cache
- Backend API service
- Frontend development server

#### Verify Services
```powershell
docker-compose ps
```

### 5. Database Setup

#### Run Migrations
```powershell
cd backend
alembic upgrade head
```

#### Load Initial Data
```powershell
python scripts/seed_data.py
```

## Development Workflow

### 1. Start Development Servers

#### Backend
```powershell
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```powershell
cd frontend
npm run dev
```

### 2. Access Development Environment
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend: http://localhost:3000

### 3. Development Tools

#### Database Management
- pgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081

#### Monitoring
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

### 4. Running Tests
```powershell
# Run backend tests
cd backend
pytest

# Run frontend tests
cd frontend
npm test
```

## Common Issues and Solutions

### Database Connection Issues
1. Verify PostgreSQL container is running:
```powershell
docker-compose ps
```

2. Check database logs:
```powershell
docker-compose logs deals_postgres
```

3. Verify connection settings in `.env`

### Redis Connection Issues
1. Check Redis container status:
```powershell
docker-compose ps deals_redis
```

2. Verify Redis connection in `.env`

### API Key Configuration
1. Ensure all required API keys are set in `.env`
2. Verify key permissions and quotas
3. Check API service status

## Development Best Practices

### Code Style
- Follow PEP 8 for Python code
- Use ESLint and Prettier for JavaScript/TypeScript
- Follow project-specific coding standards
- Use type hints consistently

### Git Workflow
1. Create feature branch from develop
2. Make changes and commit
3. Run tests and linting
4. Create pull request
5. Address review comments
6. Merge after approval

### Documentation
- Update API documentation for endpoint changes
- Document new environment variables
- Update README for significant changes
- Include testing instructions

### Testing
- Write unit tests for new features
- Update integration tests
- Test in development environment
- Verify documentation accuracy

## Support and Resources

### Documentation
- [API Documentation](../api/overview.md)
- [Database Schema](../database/schema.md)
- [Agent System](../agents/overview.md)
- [Testing Guide](../testing/strategy.md)

### Getting Help
1. Check existing documentation
2. Review common issues
3. Contact development team
4. Create GitHub issue 