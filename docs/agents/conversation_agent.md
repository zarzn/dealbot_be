# Conversation Agent

## Overview

The Conversation Agent is a critical component of the AI Agentic Deals System that enables natural language interactions between users and the platform. It interprets user queries, extracts intent, coordinates with other specialized agents, and generates contextually relevant responses in a conversational format.

The agent leverages advanced language understanding capabilities to maintain context across multi-turn interactions, allowing users to have fluid conversations about deals, products, preferences, and goals without needing to use rigid command structures or specialized syntax.

## Architecture

The Conversation Agent follows a modular architecture that integrates with the broader agent ecosystem:

```
┌─────────────────────────┐      ┌──────────────────────┐     ┌─────────────────────┐
│                         │      │                      │     │                     │
│    User Interface       │──────│   Conversation Agent │─────│  Specialized Agents │
│    (Chat, Commands)     │      │   (Context Manager)  │     │  (Deal, Goal, etc.) │
│                         │      │                      │     │                     │
└─────────────────────────┘      └──────────────────────┘     └─────────────────────┘
                                          │                             │
                                          │                             │
                                          ▼                             ▼
                                 ┌──────────────────┐        ┌─────────────────────┐
                                 │                  │        │                     │
                                 │    LLM Service   │        │   Data Services     │
                                 │                  │        │                     │
                                 └──────────────────┘        └─────────────────────┘
```

### Core Components

1. **Context Manager**: Maintains conversation history and user context across multiple interactions.
2. **Intent Classifier**: Analyzes user queries to determine the underlying intent and required action.
3. **Agent Coordinator**: Routes requests to specialized agents based on recognized intent and coordinates multi-agent responses.
4. **Response Generator**: Transforms structured data from specialized agents into natural language responses.
5. **Memory System**: Stores important conversation artifacts for reference in future interactions.

### Technology Stack

The Conversation Agent is built on the following technologies:

- **Primary LLM**: DeepSeek R1 for natural language understanding and generation
- **Fallback LLM**: GPT-4 when primary model fails or for specialized tasks
- **Redis**: For caching conversation history and session management
- **PostgreSQL**: For persistent storage of conversation artifacts and user preferences
- **FastAPI**: For webhook endpoints that receive and respond to conversation events
- **Pydantic**: For input/output validation and schema enforcement

## Core Capabilities

### Natural Language Understanding
- Intent detection and classification
- Entity extraction (products, price ranges, dates, preferences)
- Context-aware interpretation of ambiguous queries
- Handling of colloquialisms and conversational language

### Context Management
- Maintenance of conversation history and state
- Reference resolution for pronouns and implicit entities 
- Recovery of conversation threads after interruptions
- Topic tracking and context switching

### Intelligent Response Generation
- Natural language generation based on structured data
- Personalization based on user preferences and history
- Adaptive response detail level based on user expertise
- Multi-format responses (text, structured data, suggestions)

### Multi-Agent Coordination
- Delegation to specialized agents for domain-specific tasks
- Aggregation of responses from multiple specialized agents
- Conflict resolution when agents provide contradictory information
- Sequential and parallel agent workflows based on task complexity

## Implementation Details

### Conversation Flow

1. **User Query**: A natural language query is received from the user interface.
2. **Context Enrichment**: The query is enriched with conversation history and user profile data.
3. **Intent Classification**: The system classifies the user's intent (e.g., search deals, compare prices, get recommendations).
4. **Agent Selection**: Based on intent, the appropriate specialized agent(s) are selected.
5. **Query Processing**: Selected agents process the enhanced query and return structured responses.
6. **Response Generation**: Structured responses are transformed into natural language.
7. **Context Update**: Conversation history is updated to include the new interaction.
8. **Response Delivery**: The final response is delivered to the user.

### Conversation Context Management

The agent maintains a context object for each conversation with the following structure:

```python
{
    "conversation_id": "unique_identifier",
    "user_id": "user_identifier",
    "session_data": {
        "start_time": "timestamp",
        "last_interaction": "timestamp",
        "interaction_count": 0
    },
    "history": [
        {
            "role": "user|system|assistant",
            "content": "message content",
            "timestamp": "timestamp",
            "metadata": {}
        }
    ],
    "active_entities": {
        "deals": [{"id": "deal_id", "title": "deal title", ...}],
        "goals": [{"id": "goal_id", "title": "goal title", ...}],
        "preferences": {"price_range": [min, max], "brands": [...], ...}
    },
    "state": {
        "current_topic": "deals|goals|preferences|...",
        "pending_questions": [],
        "flagged_for_follow_up": []
    }
}
```

This context is stored in Redis for active sessions and persisted to PostgreSQL for longer-term storage and analytics.

## API Contract

### Conversation Input

```json
{
    "conversation_id": "string | null",  // null for new conversations
    "user_id": "string",
    "message": "string",
    "metadata": {
        "source": "chat|voice|email",
        "device_info": {},
        "timezone": "string",
        "locale": "string"
    }
}
```

### Conversation Output

```json
{
    "conversation_id": "string",
    "response": "string",
    "suggestions": ["string"],
    "data": {
        "deals": [],
        "goals": [],
        "actions": []
    },
    "metadata": {
        "intent": "string",
        "confidence": 0.95,
        "processing_time_ms": 450,
        "agents_consulted": ["deal_agent", "goal_agent"]
    }
}
```

## Performance Requirements

1. **Response Time**:
   - Average response time: < 1.5 seconds
   - 95th percentile: < 3 seconds
   - 99th percentile: < 5 seconds

2. **Throughput**:
   - Support for at least 100 concurrent conversations
   - Ability to handle spikes of up to 500 requests per minute

3. **Accuracy**:
   - Intent classification accuracy: > 90%
   - Entity extraction accuracy: > 85%
   - Response satisfaction rating: > 4.2/5.0

## Error Handling

The Conversation Agent implements robust error handling with graceful degradation:

1. **LLM Failure**: Falls back to secondary LLM model or template-based responses
2. **Specialized Agent Unavailability**: Returns partial information with clear explanation
3. **Context Loss**: Ability to rebuild context from minimal information
4. **Ambiguous Queries**: Requests clarification with structured options
5. **Unsupported Intents**: Clearly communicates limitations and suggests alternatives

## Monitoring Metrics

The following metrics are tracked to monitor agent performance:

1. **Usage Metrics**:
   - Conversation count (daily, weekly, monthly)
   - Messages per conversation
   - Active users
   - Peak conversation times

2. **Performance Metrics**:
   - Response time (average, 95th, 99th percentile)
   - LLM token usage
   - Cache hit rate
   - Error rate by type

3. **Engagement Metrics**:
   - Conversation completion rate
   - Task success rate
   - Follow-up question rate
   - User satisfaction ratings

## Integration Points

The Conversation Agent integrates with several other system components:

1. **Frontend Chat Interface**: Receives user messages and displays responses
2. **Specialized Agents**:
   - Deal Search Agent: For finding and recommending deals
   - Goal Analysis Agent: For managing user goals
   - Price Analysis Agent: For price trend analysis
   - Notification Agent: For setting up alerts and notifications

3. **Core Services**:
   - Authentication Service: For user identity and permissions
   - Token Service: For tracking token usage
   - Analytics Service: For reporting on conversation patterns

## Future Enhancements

1. **Multi-modal Conversations**: Support for images and voice input/output
2. **Proactive Recommendations**: Initiate conversations based on user preferences and market changes
3. **Conversation Summarization**: Provide concise summaries of past conversations
4. **Personalization Improvements**: Learning user preferences from conversation patterns
5. **Multi-language Support**: Expand beyond English to major global languages
6. **Advanced Entity Linking**: Connect mentioned entities to knowledge graph

## Testing Strategy

### Unit Testing

1. **Intent Classification**: Verify correct identification of intents from sample utterances
2. **Entity Extraction**: Test extraction of entities from varied phrasings
3. **Context Management**: Validate proper maintenance of conversation state
4. **Response Generation**: Test transformation of structured data to natural language

### Integration Testing

1. **Agent Coordination**: Verify proper routing to specialized agents
2. **End-to-end Conversations**: Test complete conversation flows for common scenarios
3. **Error Handling**: Validate graceful degradation in failure scenarios
4. **Performance**: Benchmark response times and throughput under load

### Performance Testing

1. **Load Testing**: Verify handling of concurrent conversations
2. **Latency Testing**: Measure response time under various conditions
3. **Stress Testing**: Determine breaking points and recovery behavior
4. **Endurance Testing**: Evaluate performance over extended periods

## Development Guidelines

1. **Modularity**: Keep components loosely coupled for easier testing and maintenance
2. **Observability**: Implement comprehensive logging and monitoring
3. **Configurability**: Make behavior configurable without code changes
4. **Testability**: Design interfaces with testing in mind
5. **Scalability**: Implement stateless design where possible to enable horizontal scaling
6. **Security**: Sanitize all user inputs and implement proper authentication controls
7. **Documentation**: Maintain up-to-date technical and user-facing documentation

## Resources

- API Documentation: `/api/v1/conversation`
- Internal Classes: `ConversationAgent`, `ConversationContext`, `ConversationTools`
- Configuration: Settings in `conversation_config.py`
- Deployment: Part of the main agent service container 