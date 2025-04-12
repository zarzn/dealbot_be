# CI/CD Pipeline Documentation

## Overview

This document outlines the Continuous Integration and Continuous Deployment (CI/CD) pipeline used for the AI Agentic Deals System. The pipeline automates the process of building, testing, and deploying changes to different environments, ensuring consistent, reliable, and efficient delivery of new features and fixes.

## Pipeline Architecture

The CI/CD pipeline is implemented using GitHub Actions and AWS services, providing a streamlined workflow from code commit to production deployment. The pipeline follows these key principles:

1. **Automation First**: All repetitive tasks are automated
2. **Quality Gates**: Code must pass all tests and quality checks before deployment
3. **Environment Isolation**: Clear separation between development, staging, and production
4. **Observability**: Comprehensive logging and monitoring of pipeline execution
5. **Rollback Capability**: Ability to quickly revert changes if issues are detected

### Pipeline Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │     │             │     │             │
│    Code     │────►│    Build    │────►│    Test     │────►│   Deploy    │────►│   Verify    │
│   Commit    │     │             │     │             │     │             │     │             │
│             │     │             │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                                       ▲                                       │
       │                                       │                                       │
       │                                       │                                       │
       │                                       │                                       ▼
       │                                       │                                ┌─────────────┐
       │                                       │                                │             │
       └───────────────────────────────────────┘◄───────────────────────────────┤  Rollback   │
                                                                                │  (if needed)│
                                                                                │             │
                                                                                └─────────────┘
```

## GitHub Actions Workflows

The pipeline is implemented using several GitHub Actions workflows, each responsible for specific stages of the CI/CD process.

### 1. Continuous Integration Workflow

**File**: `.github/workflows/ci.yml`

This workflow runs on every pull request to the main branch and on direct pushes to the main branch.

```yaml
name: Continuous Integration

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint:
    name: Lint Code
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements-dev.txt
      - name: Run linting
        run: |
          cd backend
          flake8 .
          black --check .
          isort --check .

  test-backend:
    name: Test Backend
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:6
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements-dev.txt
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
          TEST_MODE: true
          DEEPSEEK_API_KEY: ${{ secrets.TEST_DEEPSEEK_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.TEST_OPENAI_API_KEY }}
        run: |
          cd backend
          pytest -xvs

  test-frontend:
    name: Test Frontend
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run tests
        run: |
          cd frontend
          npm test

  build:
    name: Build Artifacts
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - uses: actions/checkout@v3
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      - name: Build and push backend image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: agentic-deals-backend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      - name: Build frontend
        run: |
          cd frontend
          npm ci
          npm run build
      - name: Store frontend build artifacts
        uses: actions/upload-artifact@v3
        with:
          name: frontend-build
          path: frontend/build
```

### 2. Staging Deployment Workflow

**File**: `.github/workflows/deploy-staging.yml`

This workflow automatically deploys changes to the staging environment when pushes are made to the `develop` branch.

```yaml
name: Deploy to Staging

on:
  push:
    branches: [ develop ]
  workflow_dispatch:

jobs:
  deploy-backend-staging:
    name: Deploy Backend to Staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Update ECS service
        run: |
          aws ecs update-service --cluster agentic-deals-cluster-staging \
            --service agentic-deals-service-staging \
            --force-new-deployment \
            --no-cli-pager
      - name: Wait for ECS deployment to complete
        run: |
          aws ecs wait services-stable \
            --cluster agentic-deals-cluster-staging \
            --services agentic-deals-service-staging \
            --no-cli-pager

  deploy-frontend-staging:
    name: Deploy Frontend to Staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies and build
        env:
          REACT_APP_API_URL: https://staging-api.agenticdeals.com
          REACT_APP_ENVIRONMENT: staging
        run: |
          cd frontend
          npm ci
          npm run build
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Deploy to S3
        run: |
          aws s3 sync frontend/build/ s3://agentic-deals-staging-frontend/ --delete
      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.STAGING_CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/*" \
            --no-cli-pager
```

### 3. Production Deployment Workflow

**File**: `.github/workflows/deploy-production.yml`

This workflow deploys to production when triggered manually or on a release tag.

```yaml
name: Deploy to Production

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      confirm:
        description: 'Type "yes" to confirm production deployment'
        required: true
        default: 'no'

jobs:
  verify-deployment:
    name: Verify Deployment Confirmation
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'
    steps:
      - name: Check confirmation
        if: github.event.inputs.confirm != 'yes'
        run: |
          echo "Production deployment requires confirmation with 'yes'"
          exit 1

  deploy-backend-production:
    name: Deploy Backend to Production
    needs: [verify-deployment]
    if: always() && (needs.verify-deployment.result == 'success' || needs.verify-deployment.result == 'skipped')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Update ECS service
        run: |
          aws ecs update-service --cluster agentic-deals-cluster \
            --service agentic-deals-service \
            --force-new-deployment \
            --no-cli-pager
      - name: Wait for ECS deployment to complete
        run: |
          aws ecs wait services-stable \
            --cluster agentic-deals-cluster \
            --services agentic-deals-service \
            --no-cli-pager

  deploy-frontend-production:
    name: Deploy Frontend to Production
    needs: [deploy-backend-production]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies and build
        env:
          REACT_APP_API_URL: https://api.agenticdeals.com
          REACT_APP_ENVIRONMENT: production
        run: |
          cd frontend
          npm ci
          npm run build
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Deploy to S3
        run: |
          aws s3 sync frontend/build/ s3://agentic-deals-production-frontend/ --delete
      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.PRODUCTION_CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/*" \
            --no-cli-pager

  verify-deployment:
    name: Verify Production Deployment
    needs: [deploy-backend-production, deploy-frontend-production]
    runs-on: ubuntu-latest
    steps:
      - name: Check backend health
        run: |
          curl --fail https://api.agenticdeals.com/health || exit 1
      - name: Check frontend
        run: |
          curl --fail https://agenticdeals.com || exit 1
      - name: Notify deployment success
        if: success()
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_CHANNEL: deployments
          SLACK_TITLE: Production Deployment Successful
          SLACK_MESSAGE: "🚀 AI Agentic Deals System has been successfully deployed to production!"
          SLACK_COLOR: good
      - name: Notify deployment failure
        if: failure()
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_CHANNEL: deployments
          SLACK_TITLE: Production Deployment Failed
          SLACK_MESSAGE: "🚨 Production deployment failed! Please check the logs."
          SLACK_COLOR: danger
```

### 4. Database Migration Workflow

**File**: `.github/workflows/db-migration.yml`

This workflow handles database migrations for different environments.

```yaml
name: Database Migration

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to run migrations against'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production
      confirm:
        description: 'Type "yes" to confirm production migration'
        required: true
        default: 'no'

jobs:
  verify-production:
    name: Verify Production Migration
    runs-on: ubuntu-latest
    if: github.event.inputs.environment == 'production'
    steps:
      - name: Check confirmation
        if: github.event.inputs.confirm != 'yes'
        run: |
          echo "Production migrations require confirmation with 'yes'"
          exit 1

  run-migration:
    name: Run Database Migration
    needs: [verify-production]
    if: always() && (needs.verify-production.result == 'success' || needs.verify-production.result == 'skipped')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Get database credentials
        id: db-creds
        run: |
          if [ "${{ github.event.inputs.environment }}" == "production" ]; then
            echo "DB_SECRET_ARN=${{ secrets.PROD_DB_SECRET_ARN }}" >> $GITHUB_ENV
          else
            echo "DB_SECRET_ARN=${{ secrets.STAGING_DB_SECRET_ARN }}" >> $GITHUB_ENV
          fi
          
          DB_CREDS=$(aws secretsmanager get-secret-value --secret-id $DB_SECRET_ARN --query SecretString --output text)
          
          DB_HOST=$(echo $DB_CREDS | jq -r .host)
          DB_PORT=$(echo $DB_CREDS | jq -r .port)
          DB_NAME=$(echo $DB_CREDS | jq -r .dbname)
          DB_USER=$(echo $DB_CREDS | jq -r .username)
          DB_PASSWORD=$(echo $DB_CREDS | jq -r .password)
          
          echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME" >> $GITHUB_ENV
      - name: Run database migrations
        env:
          PYTHONPATH: backend
        run: |
          cd backend
          alembic upgrade head
      - name: Verify migration success
        run: |
          cd backend
          python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; from alembic.runtime.migration import MigrationContext; import sqlalchemy as sa; config = Config('alembic.ini'); config.set_main_option('sqlalchemy.url', '${{ env.DATABASE_URL }}'); script = ScriptDirectory.from_config(config); engine = sa.create_engine('${{ env.DATABASE_URL }}'); with engine.connect() as conn: context = MigrationContext.configure(conn); current_rev = context.get_current_revision(); head_rev = script.get_current_head(); print(f'Current revision: {current_rev}'); print(f'Head revision: {head_rev}'); assert current_rev == head_rev, 'Migration failed: Database is not at head revision'"
```

## Deployment Environments

The CI/CD pipeline deploys to several environments, each serving a specific purpose in the development lifecycle.

### Development Environment

- **Purpose**: Day-to-day development and testing
- **Deployment**: Manual or local
- **Database**: Local PostgreSQL instance
- **URL**: localhost:3000 (frontend), localhost:8000 (backend)
- **Deployment Frequency**: Continuous

### Staging Environment

- **Purpose**: Pre-production testing and validation
- **Deployment**: Automated via CI/CD on pushes to `develop` branch
- **Database**: RDS PostgreSQL instance (staging)
- **URL**: https://staging.agenticdeals.com
- **Deployment Frequency**: Multiple times per day

### Production Environment

- **Purpose**: Live system used by end users
- **Deployment**: Manual trigger or release tag via CI/CD
- **Database**: RDS PostgreSQL instance (production)
- **URL**: https://agenticdeals.com
- **Deployment Frequency**: On demand, typically weekly

## Infrastructure as Code

The infrastructure for all environments is defined using AWS CloudFormation and Terraform, enabling consistent deployments and environment parity. Key infrastructure components include:

1. **ECS Cluster**: For running backend containers
2. **RDS PostgreSQL**: Database instances
3. **ElastiCache Redis**: For caching and session management
4. **S3 Buckets**: For frontend static assets
5. **CloudFront**: For content delivery
6. **API Gateway**: For API management
7. **IAM Roles**: For service permissions
8. **CloudWatch**: For logging and monitoring

## Deployment Artifacts

### Backend Artifacts

- **Docker Image**: The backend is packaged as a Docker image and pushed to Amazon ECR
- **Image Tagging**:
  - `latest`: Always points to the latest build
  - `commit-sha`: Unique tag for each build (e.g., `5a7b9c1`)
  - `release-version`: For released versions (e.g., `v1.2.3`)

### Frontend Artifacts

- **Static Files**: The frontend is built as static HTML, CSS, and JavaScript files
- **S3 Deployment**: Files are deployed to S3 buckets for different environments
- **CloudFront Distribution**: Serves frontend assets with caching

## Deployment Rollback

### Automated Rollback

The CI/CD pipeline includes automated rollback capabilities if a deployment fails or if issues are detected after deployment.

1. **Backend Rollback**:
   - ECS task definition rollback to the previous version
   - Triggered automatically if health checks fail after deployment

2. **Frontend Rollback**:
   - S3 bucket versioning allows restoration of previous frontend builds
   - CloudFront cache invalidation to ensure users get the rolled back version

### Manual Rollback

For situations requiring manual intervention:

1. **Backend**:
   ```bash
   aws ecs update-service --cluster agentic-deals-cluster \
     --service agentic-deals-service \
     --task-definition agentic-deals-task-definition:PREVIOUS_VERSION \
     --no-cli-pager
   ```

2. **Frontend**:
   ```bash
   # Return to previous S3 version
   aws s3 cp s3://agentic-deals-production-frontend/backup/ s3://agentic-deals-production-frontend/ --recursive
   
   # Invalidate CloudFront cache
   aws cloudfront create-invalidation \
     --distribution-id DISTRIBUTION_ID \
     --paths "/*" \
     --no-cli-pager
   ```

## Release Management

### Versioning Strategy

The project follows Semantic Versioning (SemVer):

- **Major Version**: Breaking changes (e.g., `2.0.0`)
- **Minor Version**: New features, backward compatible (e.g., `1.2.0`)
- **Patch Version**: Bug fixes, backward compatible (e.g., `1.1.3`)

### Release Process

1. **Create Release Branch**:
   ```bash
   git checkout -b release/v1.2.0 develop
   ```

2. **Version Bump**:
   - Update version in package.json (frontend)
   - Update version in pyproject.toml (backend)
   - Update CHANGELOG.md

3. **Create Pull Request**: Merge release branch to main

4. **Create GitHub Release**: Tag with version number and publish release

5. **Automated Deployment**: Release triggers production deployment workflow

## Security Considerations

### Secret Management

- **AWS Secrets Manager**: Stores database credentials and API keys
- **GitHub Secrets**: Stores sensitive variables for CI/CD
- **Runtime Environment Variables**: Injected at deployment time

### Scanning and Validation

- **SAST**: Static Application Security Testing with GitHub CodeQL
- **Container Scanning**: Docker images scanned for vulnerabilities
- **Dependency Checking**: NPM and Python packages checked for security issues

## Monitoring and Logging

### Deployment Monitoring

- **CloudWatch Alarms**: Alert on deployment failures
- **Slack Notifications**: Real-time updates on deployment status
- **Deployment History**: Available in GitHub Actions logs

### Application Monitoring

- **CloudWatch Logs**: Centralized logging for all components
- **CloudWatch Metrics**: Performance and health metrics
- **AWS X-Ray**: Distributed tracing for request flows

## Best Practices

1. **Never Deploy on Friday**: Avoid deploying to production before weekends
2. **One Change at a Time**: Deploy small, incremental changes
3. **Test in Staging First**: Always verify in staging before production
4. **Automate Everything**: Minimize manual steps in the deployment process
5. **Monitor After Deployment**: Watch for issues immediately after deployment
6. **Document All Changes**: Keep CHANGELOG.md updated with all changes
7. **Code Freeze Periods**: Establish deployment blackout windows for critical business periods

## Troubleshooting

### Common Issues

1. **Failed Health Checks**:
   - Check application logs in CloudWatch
   - Verify database connectivity
   - Check for resource constraints

2. **Database Migration Failures**:
   - Review migration scripts
   - Check database permissions
   - Run migrations manually if necessary

3. **Frontend Deployment Issues**:
   - Verify S3 bucket permissions
   - Check CloudFront distribution settings
   - Confirm build process completed successfully

### Support Contacts

- **DevOps Team**: devops@agenticdeals.com
- **Slack Channel**: #deployments
- **On-Call Schedule**: Available in PagerDuty

## References

1. [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
2. [GitHub Actions Documentation](https://docs.github.com/en/actions)
3. [AWS Deployment Guide](./aws_deployment.md)
4. [Docker Configuration](./docker.md)
5. [Frontend Deployment](./frontend_deployment.md) 