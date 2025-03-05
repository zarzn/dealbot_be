# Frontend Documentation

This document provides comprehensive information about the frontend architecture, components, and integration points with the backend for the AI Agentic Deals System.

## Technology Stack

The frontend is built with the following technologies:

- **React**: Core UI library
- **Next.js**: React framework for server-side rendering
- **TypeScript**: Type-safe JavaScript
- **Chakra UI**: Component library for consistent design
- **React Query**: Data fetching and state management
- **Zustand**: Lightweight state management
- **Axios**: HTTP client for API requests
- **React Hook Form**: Form validation and management
- **Chart.js**: Data visualization
- **Socket.io-client**: Real-time communication with backend

## Project Structure

The frontend codebase is organized as follows:

```
frontend/
  ├── public/          # Static assets
  ├── src/             # Source code
  │   ├── api/         # API integration
  │   ├── components/  # Reusable UI components
  │   ├── contexts/    # React contexts
  │   ├── hooks/       # Custom React hooks
  │   ├── layouts/     # Page layouts
  │   ├── pages/       # Next.js pages
  │   ├── store/       # Global state management
  │   ├── styles/      # Global styles
  │   ├── types/       # TypeScript types
  │   └── utils/       # Utility functions
  ├── .env.local       # Local environment variables
  ├── .env.development # Development environment variables
  ├── .env.production  # Production environment variables
  ├── next.config.js   # Next.js configuration
  ├── package.json     # Dependencies and scripts
  └── tsconfig.json    # TypeScript configuration
```

## Core Components

### Authentication

Authentication is handled via JWT tokens with the following components:

- `AuthContext` (`src/contexts/AuthContext.tsx`): Manages authentication state
- `useAuth` hook (`src/hooks/useAuth.ts`): Custom hook for authentication
- `ProtectedRoute` component (`src/components/ProtectedRoute.tsx`): Route protection

Authentication flow:

1. User logs in via login form
2. Backend returns JWT token
3. Token is stored in secure HTTP-only cookie
4. Token is refreshed automatically before expiration
5. Logout invalidates token on backend and removes cookie

### API Integration

API requests are managed using React Query with Axios:

- Base API configuration (`src/api/axios.ts`): Sets up base URL and interceptors
- API hooks (`src/api/hooks/`): Custom hooks for API endpoints
- Types (`src/types/api.ts`): TypeScript interfaces for API requests/responses

Example API hook:

```typescript
// src/api/hooks/useDeals.ts
export const useDeals = (filters?: DealFilters) => {
  return useQuery(['deals', filters], () => 
    api.get('/deals', { params: filters })
      .then(response => response.data),
    {
      staleTime: 5 * 60 * 1000, // 5 minutes
      keepPreviousData: true,
    }
  );
};
```

### State Management

The application uses a combination of local React state, React Query for server state, and Zustand for global UI state:

- `useAuthStore` (`src/store/authStore.ts`): Authentication state
- `useUIStore` (`src/store/uiStore.ts`): UI state (theme, sidebar, modals)
- `useNotificationStore` (`src/store/notificationStore.ts`): Notification management

Example store:

```typescript
// src/store/uiStore.ts
import create from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: 'light',
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
}));
```

### Form Handling

Forms are managed using React Hook Form with Zod for validation:

- Form components (`src/components/forms/`)
- Form schemas (`src/utils/validation.ts`)
- Custom form hooks (`src/hooks/useForm.ts`)

Example form component:

```typescript
// src/components/forms/DealForm.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { dealSchema } from '../../utils/validation';

export const DealForm = ({ onSubmit, initialData }) => {
  const { 
    register, 
    handleSubmit, 
    formState: { errors } 
  } = useForm({
    resolver: zodResolver(dealSchema),
    defaultValues: initialData || {},
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Form fields */}
    </form>
  );
};
```

## Pages and Routing

The application uses Next.js pages router with the following main pages:

- `/` - Dashboard
- `/deals` - Deals listing
- `/deals/[id]` - Deal details
- `/goals` - Goals listing
- `/goals/[id]` - Goal details
- `/analytics` - Analytics dashboard
- `/agents` - Agent management
- `/settings` - User settings
- `/auth/login` - Login page
- `/auth/register` - Registration page

Dynamic routes use Next.js slugs with data fetching in `getServerSideProps` or client-side data fetching with React Query:

```typescript
// src/pages/deals/[id].tsx
export const getServerSideProps: GetServerSideProps = async (context) => {
  const id = context.params?.id as string;
  
  try {
    // Pre-fetch deal data on the server
    const dealData = await fetchDealById(id);
    
    return {
      props: {
        dealData,
      },
    };
  } catch (error) {
    return {
      notFound: true,
    };
  }
};
```

## Real-time Updates

The frontend connects to the backend websocket server for real-time updates:

- WebSocket context (`src/contexts/WebSocketContext.tsx`)
- WebSocket hook (`src/hooks/useWebSocket.ts`)

The WebSocket handles the following events:

- Deal updates
- Goal and task status changes
- Market data updates
- Notifications

Example WebSocket hook:

```typescript
// src/hooks/useWebSocket.ts
export const useWebSocket = () => {
  const { socket } = useContext(WebSocketContext);
  
  const subscribeToDealUpdates = useCallback((dealId: string, callback: (data: any) => void) => {
    if (!socket) return;
    
    socket.emit('subscribe:deal', { dealId });
    socket.on(`deal:${dealId}:update`, callback);
    
    return () => {
      socket.off(`deal:${dealId}:update`);
      socket.emit('unsubscribe:deal', { dealId });
    };
  }, [socket]);
  
  return { 
    subscribeToDealUpdates,
    // Other websocket methods
  };
};
```

## Error Handling

The frontend implements a robust error handling system:

- Global error boundary (`src/components/ErrorBoundary.tsx`)
- API error handling in React Query
- Form validation errors with React Hook Form
- Toast notifications for user feedback

API error handling example:

```typescript
// src/api/axios.ts
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const { response } = error;
    
    if (response && response.status === 401) {
      // Handle unauthorized errors
      authStore.logout();
      window.location.href = '/auth/login';
    }
    
    if (response && response.data && response.data.message) {
      // Show error message to user
      notificationStore.addNotification({
        title: 'Error',
        message: response.data.message,
        type: 'error',
      });
    }
    
    return Promise.reject(error);
  }
);
```

## Theme and Styling

The application uses Chakra UI with a custom theme:

- Theme configuration (`src/styles/theme.ts`)
- Global styles (`src/styles/globals.css`)
- Component styles (`src/components/[ComponentName]/styles.ts`)

Theme configuration example:

```typescript
// src/styles/theme.ts
import { extendTheme } from '@chakra-ui/react';

const theme = extendTheme({
  colors: {
    brand: {
      50: '#e0f5ff',
      100: '#b8e2ff',
      // ...other shades
      900: '#0a2d4d',
    },
    // ...other color scales
  },
  fonts: {
    heading: 'Inter, system-ui, sans-serif',
    body: 'Inter, system-ui, sans-serif',
  },
  components: {
    Button: {
      // Custom button variants
    },
    // ...other component customizations
  },
});

export default theme;
```

## Feature Modules

### Dashboard

The dashboard (`/pages/index.tsx`) displays:

- Deal overview cards
- Recent activities
- Market trends
- Agent status

Components:
- `DealSummaryCard`
- `ActivityFeed`
- `MarketTrends`
- `AgentStatusCard`

### Deal Management

Deal management pages include:

- Deal listing (`/pages/deals/index.tsx`)
- Deal creation (`/pages/deals/new.tsx`)
- Deal details (`/pages/deals/[id].tsx`)

Components:
- `DealList`
- `DealForm`
- `DealDetails`
- `DealScoreCard`
- `DealActivityTimeline`

### Goal Management

Goal management pages include:

- Goal listing (`/pages/goals/index.tsx`)
- Goal creation (`/pages/goals/new.tsx`)
- Goal details (`/pages/goals/[id].tsx`)

Components:
- `GoalList`
- `GoalForm`
- `GoalDetails`
- `TaskList`
- `TaskForm`

### Agent Interaction

Agent interaction is handled via:

- Agent listing (`/pages/agents/index.tsx`)
- Agent details (`/pages/agents/[id].tsx`)
- Agent chat interface (`/components/AgentChat.tsx`)

Components:
- `AgentList`
- `AgentCard`
- `AgentChat`
- `MessageList`

### Analytics

Analytics are displayed using Chart.js:

- Performance metrics (`/pages/analytics/index.tsx`)
- Deal analytics (`/pages/analytics/deals.tsx`)
- Market analytics (`/pages/analytics/markets.tsx`)

Components:
- `PerformanceChart`
- `DealAnalyticsChart`
- `MarketTrendChart`

## Backend Integration

### API Integration

The frontend integrates with the backend API using the following endpoints:

- Authentication: `/auth/login`, `/auth/register`, `/auth/refresh`
- Deals: `/deals`, `/deals/{id}`
- Goals: `/goals`, `/goals/{id}`
- Tasks: `/tasks`, `/tasks/{id}`
- Agents: `/agents`, `/agents/{id}`
- Analytics: `/analytics`, `/analytics/deals`, `/analytics/markets`
- User: `/users/me`, `/users/settings`

Example API client:

```typescript
// src/api/deals.ts
export const fetchDeals = async (params: DealParams): Promise<DealResponse> => {
  const response = await api.get('/deals', { params });
  return response.data;
};

export const fetchDealById = async (id: string): Promise<Deal> => {
  const response = await api.get(`/deals/${id}`);
  return response.data;
};

export const createDeal = async (dealData: CreateDealRequest): Promise<Deal> => {
  const response = await api.post('/deals', dealData);
  return response.data;
};

export const updateDeal = async (id: string, dealData: UpdateDealRequest): Promise<Deal> => {
  const response = await api.put(`/deals/${id}`, dealData);
  return response.data;
};

export const deleteDeal = async (id: string): Promise<void> => {
  await api.delete(`/deals/${id}`);
};
```

### WebSocket Integration

The frontend connects to the backend WebSocket server at `/ws`:

```typescript
// src/contexts/WebSocketContext.tsx
import { createContext, useEffect, useState } from 'react';
import io, { Socket } from 'socket.io-client';
import { useAuth } from '../hooks/useAuth';

export const WebSocketContext = createContext<{ socket: Socket | null }>({ socket: null });

export const WebSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const { isAuthenticated, accessToken } = useAuth();
  
  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      if (socket) {
        socket.disconnect();
        setSocket(null);
      }
      return;
    }
    
    const socketInstance = io(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000', {
      path: '/ws',
      auth: {
        token: accessToken,
      },
    });
    
    setSocket(socketInstance);
    
    return () => {
      socketInstance.disconnect();
    };
  }, [isAuthenticated, accessToken]);
  
  return (
    <WebSocketContext.Provider value={{ socket }}>
      {children}
    </WebSocketContext.Provider>
  );
};
```

## Performance Optimizations

The frontend implements several performance optimizations:

### Code Splitting

Next.js automatic code splitting and dynamic imports:

```typescript
// src/pages/deals/[id].tsx
import dynamic from 'next/dynamic';

const DealChart = dynamic(() => import('../../components/DealChart'), {
  ssr: false,
  loading: () => <div>Loading chart...</div>,
});
```

### Memoization

React's memoization to prevent unnecessary re-renders:

```typescript
// src/components/DealList.tsx
const MemoizedDealItem = React.memo(DealItem);

export const DealList = ({ deals }) => {
  return (
    <div>
      {deals.map(deal => (
        <MemoizedDealItem key={deal.id} deal={deal} />
      ))}
    </div>
  );
};
```

### Request Optimizations

Request optimization with React Query's caching and deduplication:

```typescript
// src/hooks/useDeal.ts
export const useDeal = (id: string) => {
  return useQuery(
    ['deal', id],
    () => api.get(`/deals/${id}`).then(res => res.data),
    {
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    }
  );
};
```

### Infinite Loading

Infinite scrolling for large data sets:

```typescript
// src/hooks/useInfiniteDeals.ts
export const useInfiniteDeals = (filters?: DealFilters) => {
  return useInfiniteQuery(
    ['infiniteDeals', filters],
    ({ pageParam = 1 }) => api.get('/deals', {
      params: {
        ...filters,
        page: pageParam,
        limit: 10,
      },
    }).then(res => res.data),
    {
      getNextPageParam: (lastPage) => {
        if (lastPage.meta.currentPage < lastPage.meta.totalPages) {
          return lastPage.meta.currentPage + 1;
        }
        return undefined;
      },
    }
  );
};
```

## Testing

The frontend includes comprehensive testing:

### Unit Tests

Jest and React Testing Library for unit tests:

```typescript
// src/components/DealCard.test.tsx
import { render, screen } from '@testing-library/react';
import { DealCard } from './DealCard';

describe('DealCard', () => {
  it('renders deal information correctly', () => {
    const deal = {
      id: '1',
      title: 'Test Deal',
      status: 'active',
      market_type: 'stock',
      price: 100,
    };
    
    render(<DealCard deal={deal} />);
    
    expect(screen.getByText('Test Deal')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Stock')).toBeInTheDocument();
    expect(screen.getByText('$100')).toBeInTheDocument();
  });
});
```

### Integration Tests

Cypress for integration tests:

```typescript
// cypress/integration/deals.spec.ts
describe('Deals Page', () => {
  beforeEach(() => {
    cy.login();
    cy.visit('/deals');
  });
  
  it('displays deals list', () => {
    cy.get('[data-testid="deal-list"]').should('exist');
    cy.get('[data-testid="deal-card"]').should('have.length.at.least', 1);
  });
  
  it('can create a new deal', () => {
    cy.get('[data-testid="create-deal-button"]').click();
    cy.get('[data-testid="deal-form"]').should('be.visible');
    
    cy.get('input[name="title"]').type('New Test Deal');
    cy.get('select[name="market_type"]').select('stock');
    cy.get('input[name="price"]').type('150');
    
    cy.get('[data-testid="submit-button"]').click();
    
    cy.get('[data-testid="deal-card"]')
      .contains('New Test Deal')
      .should('be.visible');
  });
});
```

### End-to-End Tests

Playwright for end-to-end tests:

```typescript
// tests/e2e/deal-workflow.spec.ts
import { test, expect } from '@playwright/test';

test('complete deal workflow', async ({ page }) => {
  await page.goto('/auth/login');
  
  // Login
  await page.fill('input[name="email"]', 'test@example.com');
  await page.fill('input[name="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  // Create deal
  await page.goto('/deals/new');
  await page.fill('input[name="title"]', 'E2E Test Deal');
  await page.selectOption('select[name="market_type"]', 'stock');
  await page.fill('input[name="price"]', '200');
  await page.click('button[type="submit"]');
  
  // Verify deal was created
  await page.waitForURL(/\/deals\/[\w-]+/);
  await expect(page.locator('h1')).toContainText('E2E Test Deal');
  
  // Add goal to deal
  await page.click('[data-testid="add-goal-button"]');
  await page.fill('input[name="title"]', 'Research Market');
  await page.click('button[type="submit"]');
  
  // Verify goal was added
  await expect(page.locator('[data-testid="goal-item"]')).toContainText('Research Market');
});
```

## Accessibility

The frontend follows WCAG 2.1 AA standards:

- Semantic HTML
- Keyboard navigation
- ARIA attributes
- Color contrast compliance
- Screen reader support

Accessibility features:

```typescript
// src/components/Button.tsx
import { forwardRef } from 'react';
import { Button as ChakraButton, ButtonProps } from '@chakra-ui/react';

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, ...props }, ref) => {
    return (
      <ChakraButton
        ref={ref}
        {...props}
        sx={{
          '&:focus-visible': {
            boxShadow: '0 0 0 3px var(--chakra-colors-blue-300)',
          },
        }}
      >
        {children}
      </ChakraButton>
    );
  }
);

Button.displayName = 'Button';
```

## Deployment

The frontend is deployed using Vercel with the following configuration:

1. Production environment: `https://agentic-deals.example.com`
2. Staging environment: `https://staging.agentic-deals.example.com`
3. Development environment: `https://dev.agentic-deals.example.com`

Environment variables are managed through Vercel's dashboard:

```
# .env.production
NEXT_PUBLIC_API_URL=https://api.agentic-deals.example.com
NEXT_PUBLIC_WEBSOCKET_URL=wss://api.agentic-deals.example.com
NEXT_PUBLIC_ENVIRONMENT=production
```

## Security Considerations

The frontend implements the following security measures:

- HTTP-only cookies for JWT storage
- CSRF protection
- Content Security Policy (CSP)
- XSS protection
- Input sanitization
- HTTPS enforcement

Security implementation:

```typescript
// next.config.js
const ContentSecurityPolicy = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  font-src 'self';
  connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL};
`;

module.exports = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: ContentSecurityPolicy.replace(/\s{2,}/g, ' ').trim(),
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },
};
```

## Troubleshooting

Common issues and solutions:

### API Connection Issues

1. Check API URL in environment variables
2. Verify CORS configuration on backend
3. Check network tab for error responses
4. Verify authentication token

### State Management Issues

1. Check React Query devtools for query status
2. Verify Zustand store state
3. Check component re-rendering with React DevTools

### Build Errors

1. Check TypeScript errors
2. Verify dependency versions
3. Check Next.js build logs

## Contributing

Guidelines for contributing to the frontend:

1. Follow the project's coding standards
2. Write unit tests for new components
3. Ensure accessibility compliance
4. Document new features
5. Update type definitions
6. Run lint and type checks before committing

## References

- [React Documentation](https://reactjs.org/docs/getting-started.html)
- [Next.js Documentation](https://nextjs.org/docs)
- [TypeScript Documentation](https://www.typescriptlang.org/docs)
- [Chakra UI Documentation](https://chakra-ui.com/docs/getting-started)
- [React Query Documentation](https://react-query.tanstack.com/overview)
- [Zustand Documentation](https://github.com/pmndrs/zustand) 