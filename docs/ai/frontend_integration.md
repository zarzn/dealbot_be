# Frontend AI Integration

## Overview

This document explains how the frontend application integrates with the AI components of the Agentic Deals System, including implementation details, best practices, and examples.

## Architecture

The frontend AI integration follows these principles:

1. **Separation of Concerns**: AI interaction logic is isolated from UI components
2. **Progressive Enhancement**: Core functionality works without AI, enhanced with AI when available
3. **Performance First**: Optimized to reduce latency and improve user experience
4. **Error Resilience**: Graceful degradation when AI services are unavailable

## Component Structure

```
src/
├── api/
│   └── ai.ts             # AI service API client
├── hooks/
│   └── useAIAssistant.ts # React hook for AI interactions
├── components/
│   ├── AIEnhancedSearch/ # AI-enhanced search component
│   ├── DealAnalysis/     # Deal analysis with AI insights
│   └── RecommendationCard/ # AI recommendation display
└── utils/
    └── aiHelpers.ts      # Utility functions for AI interactions
```

## AI Service Client

The frontend communicates with backend AI services through a dedicated client:

```typescript
// src/api/ai.ts
import { apiClient } from './client';

export interface AIAnalysisRequest {
  dealId: string;
  userPreferences?: Record<string, any>;
  analysisType: 'basic' | 'comprehensive';
}

export interface AIAnalysisResponse {
  dealId: string;
  analysis: {
    summary: string;
    valueScore: number;
    keyPoints: string[];
    risksAndLimitations: string[];
  };
  tokensUsed: number;
  processingTime: number;
}

export const aiService = {
  /**
   * Request AI analysis for a specific deal
   */
  analyzeDeal: async (request: AIAnalysisRequest): Promise<AIAnalysisResponse> => {
    return apiClient.post('/api/ai/analyze-deal', request);
  },
  
  /**
   * Generate deal recommendations based on user preferences
   */
  getRecommendations: async (userId: string, limit: number = 5) => {
    return apiClient.get(`/api/ai/recommendations?userId=${userId}&limit=${limit}`);
  },
  
  /**
   * Enhance search query with AI processing
   */
  enhanceSearchQuery: async (query: string, context?: Record<string, any>) => {
    return apiClient.post('/api/ai/enhance-search', { query, context });
  }
};
```

## React Hook for AI Integration

A custom hook provides React components with AI capabilities:

```typescript
// src/hooks/useAIAssistant.ts
import { useState } from 'react';
import { aiService } from '../api/ai';
import { useTokenBalance } from './useTokenBalance';

export function useAIAssistant() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const { tokenBalance, deductTokens } = useTokenBalance();
  
  const analyzeDeal = async (dealId: string, preferences?: Record<string, any>) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await aiService.analyzeDeal({
        dealId,
        userPreferences: preferences,
        analysisType: 'comprehensive'
      });
      
      // Update token balance
      deductTokens(result.tokensUsed);
      
      setIsLoading(false);
      return result;
    } catch (err) {
      setError(err as Error);
      setIsLoading(false);
      throw err;
    }
  };
  
  // Additional AI methods...
  
  return {
    analyzeDeal,
    isLoading,
    error,
    hasEnoughTokens: (estimatedTokens: number) => tokenBalance >= estimatedTokens,
  };
}
```

## AI-Enhanced Components

### AI-Enhanced Search Component

```tsx
// src/components/AIEnhancedSearch/AIEnhancedSearch.tsx
import React, { useState } from 'react';
import { useAIAssistant } from '../../hooks/useAIAssistant';
import { SearchResults } from '../SearchResults';

export function AIEnhancedSearch() {
  const [query, setQuery] = useState('');
  const [enhancedQuery, setEnhancedQuery] = useState('');
  const [results, setResults] = useState([]);
  const { isLoading, error, enhanceSearchQuery } = useAIAssistant();
  
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      // First try to enhance the query with AI
      const enhanced = await enhanceSearchQuery(query);
      setEnhancedQuery(enhanced.query);
      
      // Use the enhanced query for search
      const searchResults = await dealService.search(enhanced.query);
      setResults(searchResults);
    } catch (err) {
      // Fallback to regular search if AI enhancement fails
      console.error('AI enhancement failed, using original query', err);
      const searchResults = await dealService.search(query);
      setResults(searchResults);
    }
  };
  
  return (
    <div className="ai-enhanced-search">
      <form onSubmit={handleSearch}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for deals..."
          className="search-input"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </form>
      
      {enhancedQuery && query !== enhancedQuery && (
        <div className="enhanced-query-notice">
          Showing results for <strong>{enhancedQuery}</strong>
        </div>
      )}
      
      {error && (
        <div className="error-message">
          Error enhancing search: {error.message}
        </div>
      )}
      
      <SearchResults results={results} />
    </div>
  );
}
```

### Deal Analysis Component

```tsx
// src/components/DealAnalysis/DealAnalysis.tsx
import React, { useEffect, useState } from 'react';
import { useAIAssistant } from '../../hooks/useAIAssistant';
import { useTokenBalance } from '../../hooks/useTokenBalance';
import { DealData } from '../../types';

interface DealAnalysisProps {
  deal: DealData;
}

export function DealAnalysis({ deal }: DealAnalysisProps) {
  const [analysis, setAnalysis] = useState(null);
  const { analyzeDeal, isLoading, error, hasEnoughTokens } = useAIAssistant();
  const { tokenBalance } = useTokenBalance();
  const estimatedTokenCost = 150; // Approximate token cost
  
  useEffect(() => {
    // Auto-analyze when component mounts if user has enough tokens
    if (deal && hasEnoughTokens(estimatedTokenCost)) {
      handleAnalyze();
    }
  }, [deal?.id]);
  
  const handleAnalyze = async () => {
    if (!hasEnoughTokens(estimatedTokenCost)) {
      return; // Don't attempt if tokens insufficient
    }
    
    try {
      const result = await analyzeDeal(deal.id);
      setAnalysis(result.analysis);
    } catch (err) {
      console.error('Analysis failed', err);
    }
  };
  
  if (isLoading) {
    return <div className="analysis-loading">Analyzing deal...</div>;
  }
  
  if (!analysis && !isLoading) {
    return (
      <div className="analysis-prompt">
        <h3>AI Analysis</h3>
        {!hasEnoughTokens(estimatedTokenCost) ? (
          <div className="token-warning">
            Insufficient tokens for AI analysis. 
            <a href="/tokens">Get more tokens</a>
          </div>
        ) : (
          <button onClick={handleAnalyze}>
            Analyze Deal (costs ~{estimatedTokenCost} tokens)
          </button>
        )}
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="analysis-error">
        <h3>Analysis Error</h3>
        <p>{error.message}</p>
        <button onClick={handleAnalyze}>Try Again</button>
      </div>
    );
  }
  
  return (
    <div className="deal-analysis">
      <h3>AI Analysis</h3>
      
      <div className="value-score">
        <div className="score-label">Value Score</div>
        <div className="score-value">{analysis.valueScore}/100</div>
      </div>
      
      <div className="analysis-summary">
        <h4>Summary</h4>
        <p>{analysis.summary}</p>
      </div>
      
      <div className="key-points">
        <h4>Key Points</h4>
        <ul>
          {analysis.keyPoints.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      </div>
      
      <div className="risks-limitations">
        <h4>Risks & Limitations</h4>
        <ul>
          {analysis.risksAndLimitations.map((risk, i) => (
            <li key={i}>{risk}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

## Error Handling

The frontend implements these error handling strategies for AI integration:

1. **Graceful Degradation**: Fall back to non-AI functionality when AI services fail
2. **Retry Logic**: Automatically retry transient errors with exponential backoff
3. **User Feedback**: Clear error messages with recovery options
4. **Offline Support**: Cache previous AI results for offline use

Example error handling implementation:

```typescript
// src/utils/aiHelpers.ts
export async function withAIErrorHandling<T>(
  aiFunction: () => Promise<T>, 
  fallbackFunction: () => Promise<T>
): Promise<T> {
  try {
    return await aiFunction();
  } catch (error) {
    console.error('AI function failed, using fallback', error);
    
    // Track error for monitoring
    trackAIError(error);
    
    // Use fallback function
    return fallbackFunction();
  }
}

// Usage example
const searchResults = await withAIErrorHandling(
  () => aiService.enhanceAndSearch(query),
  () => dealService.basicSearch(query)
);
```

## Token Management

The frontend manages AI token usage with these components:

```tsx
// src/components/TokenDisplay/TokenDisplay.tsx
import React from 'react';
import { useTokenBalance } from '../../hooks/useTokenBalance';

export function TokenDisplay() {
  const { tokenBalance, isLoading, error } = useTokenBalance();
  
  if (isLoading) {
    return <div className="token-balance">Loading balance...</div>;
  }
  
  if (error) {
    return <div className="token-balance token-error">Error loading balance</div>;
  }
  
  return (
    <div className="token-balance">
      <span className="token-icon">🔹</span>
      <span className="token-amount">{tokenBalance}</span>
      <a href="/tokens" className="token-get-more">Get More</a>
    </div>
  );
}
```

## Performance Optimization

The frontend optimizes AI interactions with:

1. **Request Debouncing**: Limit frequency of AI requests
2. **Response Caching**: Store and reuse AI results
3. **Progressive Loading**: Show partial results while waiting for AI
4. **Background Processing**: Run AI tasks in the background

Example implementation:

```typescript
// src/hooks/useDebounced.ts
import { useState, useEffect } from 'react';

export function useDebounced<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);
  
  return debouncedValue;
}

// Usage in AI search
function AISearchComponent() {
  const [inputValue, setInputValue] = useState('');
  const debouncedSearchTerm = useDebounced(inputValue, 500);
  
  useEffect(() => {
    if (debouncedSearchTerm) {
      // Only call AI search when typing stops for 500ms
      aiService.enhanceSearchQuery(debouncedSearchTerm);
    }
  }, [debouncedSearchTerm]);
  
  // Component JSX...
}
```

## Testing AI Components

Example test for an AI-enhanced component:

```typescript
// src/components/DealAnalysis/DealAnalysis.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DealAnalysis } from './DealAnalysis';
import { useAIAssistant } from '../../hooks/useAIAssistant';
import { mockDeal, mockAnalysis } from '../../test/mocks';

// Mock the AI assistant hook
jest.mock('../../hooks/useAIAssistant');

describe('DealAnalysis Component', () => {
  beforeEach(() => {
    // Default mock implementation
    (useAIAssistant as jest.Mock).mockReturnValue({
      analyzeDeal: jest.fn().mockResolvedValue({ analysis: mockAnalysis }),
      isLoading: false,
      error: null,
      hasEnoughTokens: jest.fn().mockReturnValue(true)
    });
  });
  
  test('renders analysis when available', async () => {
    render(<DealAnalysis deal={mockDeal} />);
    
    // Should show loading initially
    expect(screen.getByText(/analyzing deal/i)).toBeInTheDocument();
    
    // Should show analysis after loading
    await waitFor(() => {
      expect(screen.getByText(/value score/i)).toBeInTheDocument();
      expect(screen.getByText(mockAnalysis.summary)).toBeInTheDocument();
    });
  });
  
  test('shows token warning when insufficient tokens', () => {
    (useAIAssistant as jest.Mock).mockReturnValue({
      analyzeDeal: jest.fn(),
      isLoading: false,
      error: null,
      hasEnoughTokens: jest.fn().mockReturnValue(false)
    });
    
    render(<DealAnalysis deal={mockDeal} />);
    
    expect(screen.getByText(/insufficient tokens/i)).toBeInTheDocument();
    expect(screen.getByText(/get more tokens/i)).toBeInTheDocument();
  });
  
  test('handles analysis errors', async () => {
    const mockError = new Error('Analysis failed');
    
    (useAIAssistant as jest.Mock).mockReturnValue({
      analyzeDeal: jest.fn().mockRejectedValue(mockError),
      isLoading: false,
      error: mockError,
      hasEnoughTokens: jest.fn().mockReturnValue(true)
    });
    
    render(<DealAnalysis deal={mockDeal} />);
    
    await waitFor(() => {
      expect(screen.getByText(/analysis error/i)).toBeInTheDocument();
      expect(screen.getByText(/analysis failed/i)).toBeInTheDocument();
    });
  });
});
```

## Best Practices

When implementing AI features in the frontend:

1. **Always provide fallbacks** for when AI services are unavailable
2. **Be transparent with users** about AI-generated content
3. **Handle loading states** with appropriate UI indicators
4. **Optimize token usage** to reduce costs
5. **Cache results** where appropriate
6. **Implement clear error handling** with recovery paths
7. **Test both success and failure scenarios**
8. **Add monitoring** for AI feature usage and errors 