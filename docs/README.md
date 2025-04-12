# AI Agentic Deals System Documentation

## Overview
An AI-powered deal monitoring system that actively searches for and tracks user-defined deals across e-commerce platforms. The system employs automated monitoring, user-defined goals, and a conversational interface to provide a personalized deal-finding experience, using a native cryptocurrency token for service access and rewards.

## LLM Configuration

The system uses multiple Language Models (LLMs) for different environments:

### Production Environment
- **Primary Model**: DeepSeek R1
- **API Key**: `DEEPSEEK_API_KEY`
- **Use Case**: Main production model
- **Features**:
  - High accuracy
  - Specialized in deal evaluation
  - Production-grade reliability

### Fallback Configuration
- **Model**: GPT-4
- **API Key**: `OPENAI_API_KEY`
- **Use Case**: Backup when primary model fails
- **Features**:
  - High reliability
  - Strong general performance
  - Used when primary model is unavailable

### Test Environment
- **Model**: Mock LLM
- **API Key**: Not required
- **Use Case**: Unit tests and CI/CD
- **Features**:
  - Fast execution
  - Deterministic responses
  - No external dependencies

## Documentation Structure

### 1. Architecture
- [System Architecture](architecture/architecture.md)
- [Component Diagram](architecture/component_diagram.md)
- [Data Flow](architecture/data_flow.md)
- [Integration Points](architecture/integration_points.md)

### 2. Development
- [Setup Guide](development/setup_guide.md)
- [Coding Standards](development/coding_standards.md)
- [Development Workflow](development/workflow.md)
- [Environment Configuration](development/environment.md)

### 3. API Documentation
- [API Overview](api/overview.md)
- [Authentication](api/authentication.md)
- [Endpoints](api/endpoints.md)
- [Models](api/models.md)
- [WebSocket](api/websocket.md)

### 4. Database
- [Schema](database/schema.md)
- [Migrations](database/migrations.md)
- [Query Optimization](database/optimization.md)
- [Connection Management](database/connection_management.md)

### 5. AI Components
- [AI Processing Pipeline](ai/processing_pipeline.md)
- [Agent System Overview](agents/overview.md)
- [Goal Analysis Agent](agents/goal_analysis.md)
- [Deal Search Agent](agents/deal_search.md)
- [Price Analysis Agent](agents/price_analysis.md)
- [Notification Agent](agents/notification.md)

### 6. Security
- [Authentication & Authorization](security/auth.md)
- [Token Management](security/tokens.md)
- [Data Protection](security/data_protection.md)
- [Security Best Practices](security/best_practices.md)

### 7. Testing
- [Testing Strategy](testing/strategy.md)
- [Unit Tests](testing/unit_tests.md)
- [Integration Tests](testing/integration_tests.md)
- [Performance Tests](testing/performance_tests.md)

### 8. Deployment
- [AWS Deployment Guide](deployment/aws_deployment.md)
- [Deployment Guide](deployment/guide.md)
- [Docker Configuration](deployment/docker.md)
- [CI/CD Pipeline](deployment/cicd.md)
- [Scaling](deployment/scaling.md)

### 9. Monitoring
- [Logging](monitoring/logging.md)
- [Metrics](monitoring/metrics.md)
- [Alerting](monitoring/alerting.md)
- [Performance Monitoring](monitoring/performance.md)

### 10. Token System
- [Token System Overview](token/system.md)
- [Token Wallet](token/wallet.md)
- [Token Balance Management](token/balance.md)
- [Token Transactions](token/transactions.md)
- [Smart Contract Integration](token/smart_contract.md)

### 11. Features
- [Deal Sharing](features/sharing.md)
- [Deal Comparison](features/comparison.md)
- [Social Features](features/social.md)
- [Export Functionality](features/export.md)

### 12. Compliance
- [GDPR Compliance](compliance/gdpr.md)
- [CCPA Compliance](compliance/ccpa.md)
- [Security Policies](compliance/security_policies.md)
- [Data Retention](compliance/data_retention.md)

## Frontend Documentation

The frontend documentation is available in MDX format and can be found in `frontend/src/markdown/docs/`. Key documents include:

- [Getting Started](../frontend/src/markdown/docs/getting-started.mdx)
- [Understanding Deal Analysis](../frontend/src/markdown/docs/understanding-deal-analysis.mdx)
- [Tracking Deals](../frontend/src/markdown/docs/tracking-deals.mdx)
- [Token System](../frontend/src/markdown/docs/token-system.mdx)
- [Sharing Deals](../frontend/src/markdown/docs/sharing-deals.mdx)
- [Searching Deals](../frontend/src/markdown/docs/searching-deals.mdx)
- [Deal Goals](../frontend/src/markdown/docs/deal-goals.mdx)
- [Troubleshooting](../frontend/src/markdown/docs/troubleshooting.mdx)
- [FAQ](../frontend/src/markdown/docs/faq.mdx)

## Quick Links
- [Getting Started](development/setup_guide.md)
- [API Reference](api/overview.md)
- [Troubleshooting](development/troubleshooting.md)
- [Contributing Guide](development/contributing.md)
- [Change Log](CHANGELOG.md)

## Support
For technical support or questions about the documentation, please contact the development team or create an issue in the project repository. 