# WebSocket API Documentation

This directory contains comprehensive documentation for the WebSocket API implementation in the AI Agentic Deals System.

## Purpose

The WebSocket API enables real-time bidirectional communication between clients and the server, providing capabilities such as:

- Real-time deal updates
- Live notifications
- Chat functionality
- Subscription-based data delivery

## Documentation Structure

This documentation is organized into the following files:

1. [**Implementation Guide**](implementation_guide.md) - Complete overview of the WebSocket API implementation
2. [**Quick Reference**](quick_reference.md) - Concise reference for message formats and available actions
3. [**Client Guide**](client_guide.md) - Detailed instructions for implementing client-side WebSocket functionality
4. [**Server Guide**](server_guide.md) - In-depth guide for implementing the server-side of the WebSocket API

## Key Features

- **Authentication** - Secure connection using JWT tokens
- **Message Routing** - Flexible routing based on action types
- **Subscriptions** - Topic-based subscription for receiving updates
- **Real-time Notifications** - Immediate delivery of system events
- **Bidirectional Messaging** - Support for chat and interactive features

## Implementation Overview

The AI Agentic Deals System implements WebSockets using:

- **AWS API Gateway** - For managing WebSocket connections
- **AWS Lambda** - For processing WebSocket events
- **DynamoDB** - For storing connection information
- **Redis** - For pub/sub capabilities

The implementation follows best practices for:
- Security
- Performance
- Scalability
- Error handling

## Getting Started

If you're new to the WebSocket API, start with:

1. First read the [Implementation Guide](implementation_guide.md)
2. Then check the [Quick Reference](quick_reference.md)
3. Depending on your needs, follow either the [Client Guide](client_guide.md) or [Server Guide](server_guide.md)

## Related Documentation

- [General API Reference](../readme.md)
- [Architecture Documentation](../../architecture/architecture.md)
- [AWS Deployment Guide](../../deployment/aws_deployment.md) 