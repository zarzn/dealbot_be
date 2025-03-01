# Frontend Architecture

## Overview
The frontend of the AI Agentic Deals System is built using Next.js 14+ with TypeScript, providing a modern, performant, and type-safe user interface. The architecture follows best practices for scalability, maintainability, and user experience.

## Tech Stack

### Core Technologies
- Next.js 14+
- TypeScript
- React Query
- Tailwind CSS
- shadcn/ui components

### State Management
- React Query for server state
- Local storage for preferences
- Context API for global state
- Zustand for complex state

## Project Structure
```
frontend/
├── app/                    # Next.js app directory
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   └── (routes)/          # Route groups
├── components/            # React components
│   ├── ui/               # UI components
│   ├── forms/            # Form components
│   ├── layouts/          # Layout components
│   └── shared/           # Shared components
├── hooks/                # Custom hooks
├── lib/                  # Utility functions
├── styles/              # Global styles
├── types/               # TypeScript types
└── public/              # Static assets
```

## Component Architecture

### 1. UI Components
```typescript
// components/ui/Button.tsx
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost';
  size: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
}

export const Button: React.FC<ButtonProps> = ({
  variant,
  size,
  loading,
  disabled,
  children,
  onClick
}) => {
  return (
    <button
      className={cn(
        buttonVariants({ variant, size }),
        loading && 'opacity-50 cursor-wait'
      )}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
};
```

### 2. Layout Components
```typescript
// components/layouts/DashboardLayout.tsx
interface DashboardLayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div className="ml-64 p-8">
        <TopBar />
        <main>{children}</main>
      </div>
    </div>
  );
};
```

## State Management

### 1. Server State
```typescript
// hooks/useGoals.ts
export function useGoals() {
  return useQuery({
    queryKey: ['goals'],
    queryFn: async () => {
      const response = await fetch('/api/v1/goals');
      if (!response.ok) throw new Error('Failed to fetch goals');
      return response.json();
    }
  });
}
```

### 2. Client State
```typescript
// stores/dealStore.ts
interface DealStore {
  selectedDeals: Deal[];
  addDeal: (deal: Deal) => void;
  removeDeal: (dealId: string) => void;
  clearDeals: () => void;
}

export const useDealStore = create<DealStore>((set) => ({
  selectedDeals: [],
  addDeal: (deal) => set((state) => ({
    selectedDeals: [...state.selectedDeals, deal]
  })),
  removeDeal: (dealId) => set((state) => ({
    selectedDeals: state.selectedDeals.filter(d => d.id !== dealId)
  })),
  clearDeals: () => set({ selectedDeals: [] })
}));
```

## API Integration

### 1. API Client
```typescript
// lib/api.ts
export const api = {
  async get<T>(endpoint: string) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        Authorization: `Bearer ${getToken()}`
      }
    });
    if (!response.ok) throw new Error('API request failed');
    return response.json() as Promise<T>;
  },
  
  async post<T>(endpoint: string, data: any) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`
      },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('API request failed');
    return response.json() as Promise<T>;
  }
};
```

### 2. API Hooks
```typescript
// hooks/useDeals.ts
export function useDeals(goalId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (deal: CreateDealDTO) =>
      api.post<Deal>(`/goals/${goalId}/deals`, deal),
    onSuccess: (newDeal) => {
      queryClient.setQueryData<Deal[]>(['deals', goalId], (old) => 
        old ? [...old, newDeal] : [newDeal]
      );
    }
  });
}
```

## Form Management

### 1. Form Components
```typescript
// components/forms/GoalForm.tsx
interface GoalFormProps {
  onSubmit: (data: GoalFormData) => void;
  initialData?: Goal;
}

export const GoalForm: React.FC<GoalFormProps> = ({ onSubmit, initialData }) => {
  const form = useForm<GoalFormData>({
    defaultValues: initialData,
    resolver: zodResolver(goalFormSchema)
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Goal Title</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {/* Other form fields */}
      </form>
    </Form>
  );
};
```

## Routing and Navigation

### 1. Route Configuration
```typescript
// app/(dashboard)/goals/[id]/page.tsx
export default async function GoalPage({
  params: { id }
}: {
  params: { id: string }
}) {
  return (
    <Suspense fallback={<GoalSkeleton />}>
      <GoalDetails id={id} />
    </Suspense>
  );
}
```

### 2. Navigation
```typescript
// components/navigation/Sidebar.tsx
export const Sidebar = () => {
  const pathname = usePathname();
  
  return (
    <nav className="fixed w-64 h-screen bg-sidebar">
      <Link
        href="/dashboard"
        className={cn(
          'nav-link',
          pathname === '/dashboard' && 'active'
        )}
      >
        Dashboard
      </Link>
      {/* Other navigation links */}
    </nav>
  );
};
```

## Error Handling

### 1. Error Boundaries
```typescript
// components/ErrorBoundary.tsx
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}
```

### 2. Error Handling Hooks
```typescript
// hooks/useErrorHandler.ts
export function useErrorHandler() {
  const toast = useToast();

  return useCallback((error: unknown) => {
    if (error instanceof ApiError) {
      toast({
        title: 'Error',
        description: error.message,
        variant: 'destructive'
      });
    } else {
      toast({
        title: 'Error',
        description: 'An unexpected error occurred',
        variant: 'destructive'
      });
    }
  }, [toast]);
}
```

## Performance Optimization

### 1. Image Optimization
```typescript
// components/DealImage.tsx
export const DealImage: React.FC<{ deal: Deal }> = ({ deal }) => {
  return (
    <Image
      src={deal.imageUrl}
      alt={deal.title}
      width={300}
      height={200}
      placeholder="blur"
      blurDataURL={deal.thumbnailUrl}
      loading="lazy"
    />
  );
};
```

### 2. Code Splitting
```typescript
// app/(dashboard)/deals/page.tsx
const DealChart = dynamic(() => import('@/components/DealChart'), {
  loading: () => <DealChartSkeleton />,
  ssr: false
});
```

## Testing

### 1. Component Tests
```typescript
// __tests__/components/Button.test.tsx
describe('Button', () => {
  it('renders correctly', () => {
    render(<Button variant="primary" size="md">Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('handles click events', () => {
    const onClick = jest.fn();
    render(
      <Button variant="primary" size="md" onClick={onClick}>
        Click me
      </Button>
    );
    fireEvent.click(screen.getByText('Click me'));
    expect(onClick).toHaveBeenCalled();
  });
});
```

### 2. Integration Tests
```typescript
// __tests__/pages/goals.test.tsx
describe('Goals Page', () => {
  it('displays goals list', async () => {
    render(<GoalsPage />);
    await waitFor(() => {
      expect(screen.getByText('My Goals')).toBeInTheDocument();
    });
  });
});
```

## Styling

### 1. Tailwind Configuration
```typescript
// tailwind.config.js
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        primary: {...},
        secondary: {...}
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography')
  ]
};
```

### 2. Global Styles
```scss
// styles/globals.scss
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn-primary {
    @apply px-4 py-2 bg-primary text-white rounded-md;
    &:hover {
      @apply bg-primary-dark;
    }
  }
}
```

## Best Practices

### 1. Code Organization
- Group related components
- Use consistent naming
- Follow component patterns
- Maintain type safety

### 2. Performance
- Implement code splitting
- Optimize images
- Use proper caching
- Monitor bundle size

### 3. Accessibility
- Use semantic HTML
- Implement ARIA labels
- Ensure keyboard navigation
- Test with screen readers

### 4. Security
- Validate user input
- Sanitize data display
- Implement CSP
- Handle sensitive data 