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
Copy-Item .env.example .env.development
```

2. Update environment variables in `.env.development` as needed. The file includes:
```env
# Application Configuration
PROJECT_NAME="AI Agentic Deals System"
VERSION="1.0.0"
DEBUG=true
ENVIRONMENT="development"

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=12345678
POSTGRES_DB=deals
POSTGRES_HOST=deals_postgres
POSTGRES_PORT=5432

# Redis Configuration
REDIS_URL=redis://deals_redis:6379/0
REDIS_HOST=deals_redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
REDIS_SSL=false

# API Keys (use dummy values for development)
AMAZON_ACCESS_KEY=dummy_key
AMAZON_SECRET_KEY=dummy_secret
WALMART_CLIENT_ID=dummy_id
WALMART_CLIENT_SECRET=dummy_secret
DEEPSEEK_API_KEY=dummy_key
OPENAI_API_KEY=dummy_key
```

3. For testing, create a test environment file:
```powershell
Copy-Item .env.example .env.test
```

4. Update `.env.test` with test-specific values:
```env
ENVIRONMENT=test
DEBUG=true
POSTGRES_DB=agentic_deals_test
POSTGRES_HOST=localhost
REDIS_HOST=localhost
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