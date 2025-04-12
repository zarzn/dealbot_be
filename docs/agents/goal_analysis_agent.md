# Goal Analysis Agent

## Overview

The Goal Analysis Agent is a specialized AI component within the AI Agentic Deals System responsible for understanding, tracking, and helping users achieve their deal-finding objectives. It transforms abstract user goals into actionable search parameters, monitors progress, and provides personalized recommendations to help users find and track deals that align with their specific needs and budget constraints.

## Architecture

### Position in the Agent System

The Goal Analysis Agent operates as a strategic component within the broader agent ecosystem:

```
┌───────────────────────┐            ┌───────────────────────┐
│                       │  consults  │                       │
│  Conversation Agent   ├───────────►│  Goal Analysis Agent  │
│                       │            │                       │
└───────────────────────┘            └───────────┬───────────┘
                                                 │
                                                 │ provides criteria
                                                 ▼
┌───────────────────────┐            ┌───────────────────────┐
│                       │ notifies   │                       │
│  Notification Agent   │◄───────────┤  Deal Search Agent    │
│                       │            │                       │
└───────────────────────┘            └───────────────────────┘
```

### Component Structure

The Goal Analysis Agent consists of several internal components:

1. **Goal Parser**: Interprets user goal statements into structured data
2. **Parameter Extractor**: Identifies key deal parameters from goal descriptions
3. **Progress Tracker**: Monitors advancement toward goal completion
4. **Recommendation Engine**: Suggests goal refinements and related opportunities
5. **Natural Language Generator**: Creates human-readable progress reports and suggestions

## Core Capabilities

### Goal Understanding and Formulation

The Goal Analysis Agent translates user-expressed goals into actionable search criteria by:

- Identifying product categories and specific items of interest
- Extracting price targets and budget constraints
- Determining timeline requirements (urgency, future purchases)
- Recognizing quality expectations and important features
- Understanding contextual factors (gifting, personal use, etc.)

### Goal Type Classification

The agent supports multiple goal types, each with specialized handling:

1. **Price Watch Goals**
   - Monitor specific products for price drops
   - Alert when prices reach target thresholds
   - Track historical price trends

2. **Category Discovery Goals**
   - Find best deals in general product categories
   - Compare value across different brands/models
   - Highlight emerging deals in areas of interest

3. **Time-Sensitive Goals**
   - Track deals with specific deadlines (Black Friday, holidays)
   - Prioritize deals expiring soon
   - Schedule notifications for upcoming sales events

4. **Budget Allocation Goals**
   - Manage spending across multiple purchase needs
   - Optimize value within fixed budget constraints
   - Recommend timing for purchases to maximize budget

### Goal Refinement

The agent helps users refine their goals through:

- Suggesting more specific parameters for better results
- Highlighting unrealistic constraints (e.g., price targets too low)
- Recommending alternative products that better match requirements
- Providing education about important features in product categories
- Adapting goals based on market trends and availability

### Progress Tracking

Monitors advancement toward goal completion through:

- Visual progress indicators for each goal
- Regular status updates and summaries
- Achievement recognition and milestone tracking
- Historical view of goal evolution and refinements
- Success metrics and optimization suggestions

## Implementation Details

### Technology Stack

The Goal Analysis Agent is implemented using:

- **Core Framework**: FastAPI for RESTful API endpoints
- **Natural Language Processing**: Custom NLP pipeline using spaCy and NLTK
- **Parameter Extraction**: Named entity recognition with domain-specific training
- **Machine Learning**: Scikit-learn for goal classification and clustering
- **LLM Integration**: DeepSeek R1 for complex goal understanding with GPT-4 fallback
- **Progress Tracking**: Time-series analysis with pandas and numpy
- **Storage**: PostgreSQL for goal data persistence with Redis caching

### Database Schema

```sql
CREATE TABLE user_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    goal_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    parameters JSONB NOT NULL,
    progress_metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    target_date TIMESTAMP WITH TIME ZONE,
    completion_date TIMESTAMP WITH TIME ZONE,
    priority INTEGER NOT NULL DEFAULT 5
);

CREATE TABLE goal_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES user_goals(id) ON DELETE CASCADE,
    update_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE goal_deals (
    goal_id UUID NOT NULL REFERENCES user_goals(id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    relevance_score FLOAT NOT NULL,
    matched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    PRIMARY KEY (goal_id, deal_id)
);
```

### API Contract

#### Goal Creation

**Endpoint:** `POST /api/v1/goals`

**Request:**
```json
{
  "title": "Gaming Laptop Under $1200",
  "description": "Looking for a gaming laptop with RTX 3060 or better, at least 16GB RAM, under $1200. Prefer 15.6 inch screen and good battery life. Need within 2 months.",
  "goal_type": "price_watch",
  "parameters": {
    "product_category": "laptop",
    "use_case": "gaming",
    "max_price": 1200,
    "min_specs": {
      "graphics": "RTX 3060",
      "ram": "16GB"
    },
    "preferences": {
      "screen_size": "15.6",
      "battery": "good"
    },
    "timeline": "2 months"
  },
  "priority": 7
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "goal_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Gaming Laptop Under $1200",
    "created_at": "2023-11-15T14:30:00Z",
    "recommendations": [
      {
        "type": "parameter_suggestion",
        "message": "Consider adding preferred brands to get more relevant results",
        "action": {
          "type": "update_parameters",
          "field": "preferences.brands",
          "value": ["Asus", "Lenovo", "MSI"]
        }
      },
      {
        "type": "search_suggestion",
        "message": "We found 15 gaming laptops that might match your criteria",
        "action": {
          "type": "view_deals",
          "search_params": {
            "category": "laptop",
            "tags": ["gaming", "RTX 3060"],
            "max_price": 1200
          }
        }
      }
    ]
  }
}
```

#### Goal Processing Flow

1. **Natural Language Processing**
   - Extract key entities (product types, features, price points)
   - Identify intent and constraints
   - Classify goal type and priority

2. **Parameter Extraction**
   - Map extracted entities to structured parameters
   - Normalize values (convert "1.2K" to 1200)
   - Apply domain knowledge (interpret "gaming laptop" as specific category)

3. **Validation and Enhancement**
   - Verify parameter consistency (resolve conflicts)
   - Add implicit parameters based on goal type
   - Apply user preferences from profile

4. **Recommendation Generation**
   - Identify potential parameter improvements
   - Find matching or similar deals
   - Generate actionable suggestions

## Error Handling

The Goal Analysis Agent implements comprehensive error handling:

### Error Types

1. **Understanding Errors**
   - Ambiguous goal statements
   - Conflicting parameters
   - Missing critical information

2. **Processing Errors**
   - Parameter extraction failures
   - Classification uncertainties
   - Normalization issues

3. **Progress Tracking Errors**
   - Data inconsistencies
   - Metric calculation failures
   - Timeline estimation issues

### Recovery Strategies

- **Clarification Requests**: Ask users to provide missing information
- **Default Parameters**: Apply sensible defaults for non-critical parameters
- **Confidence Scoring**: Only use extracted parameters with high confidence
- **Gradual Refinement**: Start with basic goals and help users enhance them
- **Logging and Review**: Log complex goals for manual review and improvement

## Monitoring and Metrics

The Goal Analysis Agent collects the following operational metrics:

- Goal creation success rate
- Parameter extraction accuracy
- Goal completion rate by type
- User engagement with recommendations
- Goal refinement frequency
- Deal match relevance scores
- Processing time for goal analysis

## Integration Points

### Inputs

- Natural language goal statements from users
- Refined goal parameters from UI interactions
- User profile data for personalization
- Market data for realistic parameter validation

### Outputs

- Structured goal definitions for search agents
- Progress updates for notification system
- Recommendations for conversation agent
- Analytics data for platform insights

## Future Enhancements

1. **Collaborative Goals**: Enable shared goals among multiple users
2. **Multi-Goal Optimization**: Balance resources across multiple concurrent goals
3. **Learning from Success**: Apply successful goal patterns to new users
4. **Predictive Goal Suggestions**: Proactively suggest goals based on user behavior
5. **Voice-Based Goal Creation**: Support spoken goal statements via voice interfaces

## Testing Strategy

### Unit Testing

- Parameter extraction accuracy
- Goal type classification
- Progress calculation logic
- Recommendation engine

### Integration Testing

- End-to-end goal creation flow
- Interaction with search and notification systems
- Database persistence and retrieval
- Cache performance

### User Experience Testing

- Goal statement interpretation accuracy
- Recommendation relevance and usefulness
- Progress reporting clarity
- Perceived goal completion success

## Development Guidelines

1. All goal types must implement the `GoalTypeInterface` for consistent handling
2. New parameter types require corresponding extraction and validation logic
3. Progress metrics must be clearly defined and consistently calculated
4. Recommendations should always include actionable next steps
5. Goal processing must complete within 3 seconds for optimal user experience
6. All user-facing text must go through the content templating system 