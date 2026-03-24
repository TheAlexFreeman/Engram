---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - react-19-overview.md
  - tanstack-query.md
  - tanstack-router.md
  - react-performance.md
  - ../devops/sentry-fullstack-observability.md
  - ../web-fundamentals/owasp-frontend-security.md
---

# Error Boundaries and Suspense in React

Error boundaries catch render errors and display fallback UIs. Suspense holds rendering until async data or code is ready. In React 19, both are meaningfully improved. This file covers placement strategy, the `react-error-boundary` library, integration with TanStack Query, and error monitoring.

---

## 1. Why class components? Why a library?

React error boundaries must be **class components** — there is no hook equivalent (as of React 19). The required lifecycle is `getDerivedStateFromError` (to show fallback UI) and `componentDidCatch` (to log the error). In practice, nobody writes these from scratch — use the `react-error-boundary` library which wraps the class component into a composable, hook-friendly API.

```bash
npm install react-error-boundary
```

---

## 2. The react-error-boundary library

### ErrorBoundary component

```typescript
import { ErrorBoundary } from "react-error-boundary";

function ErrorFallback({
  error,
  resetErrorBoundary,
}: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre style={{ color: "red" }}>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={(error, info) => {
        // Log to Sentry or other monitoring
        Sentry.captureException(error, { extra: info });
      }}
      onReset={() => {
        // Optional: run side effects when the user clicks "Try again"
        queryClient.clear();
      }}
    >
      <MainContent />
    </ErrorBoundary>
  );
}
```

### Resetting automatically on navigation

When a user navigates to a different route, you often want to clear the error state automatically rather than leaving the fallback UI frozen:

```typescript
<ErrorBoundary
  FallbackComponent={ErrorFallback}
  resetKeys={[location.pathname]}  // reset when the pathname changes
>
  <RouteContent />
</ErrorBoundary>
```

### useErrorBoundary — throw from function components

Function components can't be error boundaries but CAN throw to the nearest one using the `useErrorBoundary` hook:

```typescript
import { useErrorBoundary } from "react-error-boundary";

function UserProfile({ userId }: { userId: string }) {
  const { showBoundary } = useErrorBoundary();

  const handleEdit = async () => {
    try {
      await updateProfile(userId, data);
    } catch (error) {
      // Throw to nearest ErrorBoundary instead of handling locally
      showBoundary(error);
    }
  };

  return <button onClick={handleEdit}>Edit</button>;
}
```

### withErrorBoundary HOC

```typescript
import { withErrorBoundary } from "react-error-boundary";

const SafeChart = withErrorBoundary(ChartComponent, {
  FallbackComponent: ChartErrorFallback,
  onError: (error) => Sentry.captureException(error),
});
```

---

## 3. React 19 error handling changes

### onUncaughtError and onCaughtError on createRoot

React 19 adds two new callbacks to `createRoot` that give you global error visibility:

```typescript
// main.tsx
import { createRoot } from "react-dom/client";

const root = createRoot(document.getElementById("root")!, {
  // Fires for errors NOT caught by any ErrorBoundary
  onUncaughtError: (error, errorInfo) => {
    Sentry.captureException(error, {
      extra: { componentStack: errorInfo.componentStack },
    });
  },

  // Fires for errors caught by an ErrorBoundary (before the fallback renders)
  onCaughtError: (error, errorInfo) => {
    // Log caught errors too — useful for detecting boundary placement issues
    console.warn("Caught by ErrorBoundary:", error);
  },
});

root.render(<App />);
```

These replace the need for `window.onerror` or `window.addEventListener("unhandledrejection")` for React render errors.

### React 19 error re-throw behavior change

In React 18, caught errors were re-thrown after being caught by the ErrorBoundary (causing them to also appear in dev console as uncaught). React 19 no longer re-throws errors caught by ErrorBoundary — they appear only once. This is a usability improvement for dev debugging.

---

## 4. Suspense boundaries

Suspense suspends rendering until a promise in a child component resolves. Without a Suspense boundary, React throws an error. With one, React renders the fallback until the data arrives.

### Placement strategy

**Too coarse** (too high in the tree): entire page spinner on every data load:
```typescript
<Suspense fallback={<FullPageSpinner />}>
  <App />  // everything suspends together
</Suspense>
```

**Too fine** (too low, wrapping tiny pieces): spinner flicker everywhere:
```typescript
// Inside a big form — each field suspends independently → visual chaos
<Suspense fallback={<Spinner />}><UserNameField /></Suspense>
<Suspense fallback={<Spinner />}><EmailField /></Suspense>
```

**Right level** — suspense at data region boundaries:
```typescript
function DashboardPage() {
  return (
    <div>
      <Header />  {/* static, no suspense needed */}

      {/* Each data-heavy region gets its own boundary */}
      <Suspense fallback={<StatsCardsSkeleton />}>
        <StatsCards />
      </Suspense>

      <Suspense fallback={<RecentActivitySkeleton />}>
        <RecentActivity />
      </Suspense>
    </div>
  );
}
```

### Collocating ErrorBoundary and Suspense

Every Suspense boundary should have a sibling (or wrapping) ErrorBoundary — loading can fail:

```typescript
function DataRegion({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary FallbackComponent={DataLoadError}>
      <Suspense fallback={<DataSkeleton />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

// Usage:
<DataRegion>
  <StatsCards />
</DataRegion>
```

---

## 5. Suspense with TanStack Query

TanStack Query's `useSuspenseQuery` opts a query into Suspense mode — it throws a promise while loading (which Suspense catches) and throws an error if the query fails (which ErrorBoundary catches).

```typescript
// Instead of handling isLoading/isError manually:
function UserProfile({ userId }: { userId: string }) {
  // Throws a promise while loading, throws error if failed
  const { data: user } = useSuspenseQuery(userQueryOptions(userId));

  // data is guaranteed to be defined here — no null checks needed
  return <div>{user.email}</div>;
}

// Wrap with both boundaries:
<ErrorBoundary FallbackComponent={ErrorFallback}>
  <Suspense fallback={<ProfileSkeleton />}>
    <UserProfile userId="123" />
  </Suspense>
</ErrorBoundary>
```

### Parallel suspending queries

When multiple `useSuspenseQuery` calls are in the same component, they suspend in sequence (waterfall). Use `useSuspenseQueries` for parallel loading:

```typescript
function Dashboard() {
  // These run in parallel; component suspends until BOTH resolve
  const [{ data: user }, { data: stats }] = useSuspenseQueries({
    queries: [userQueryOptions(userId), statsQueryOptions(userId)],
  });

  return <DashboardContent user={user} stats={stats} />;
}
```

---

## 6. TanStack Router deferred data

TanStack Router's `defer()` in loaders allows showing the page immediately with some data while other data streams in:

```typescript
// routes/project/$id.tsx
export const Route = createFileRoute("/project/$id")({
  loader: async ({ params }) => {
    // Critical data — must be available before render
    const project = await fetchProject(params.id);

    // Non-critical data — defer it; page renders without waiting
    const activity = fetchActivity(params.id);  // NOT awaited

    return {
      project,
      activity: defer(activity),  // TanStack Router defer()
    };
  },
});

function ProjectPage() {
  const { project, activity } = Route.useLoaderData();

  return (
    <div>
      <ProjectHeader project={project} />

      {/* Await component renders when the deferred promise resolves */}
      <Await promise={activity} fallback={<ActivitySkeleton />}>
        {(activityData) => <ActivityFeed data={activityData} />}
      </Await>
    </div>
  );
}
```

---

## 7. useTransition + Suspense for navigation

When navigating between routes that use Suspense, the default behavior shows the Suspense fallback on every navigation — the previous content vanishes immediately and a spinner appears. `useTransition` keeps the old content visible while new content loads:

```typescript
// In TanStack Router, pending UI is handled via Router's pendingComponent
export const Route = createFileRoute("/dashboard")({
  pendingComponent: () => <DashboardSkeleton />,  // shown during navigation loading
  pendingMs: 300,                                  // delay before showing pending state
});
// This is the TanStack Router abstraction over useTransition + Suspense
```

For manual transitions:

```typescript
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const [isPending, startTransition] = useTransition();
  const navigate = useNavigate();

  return (
    <a
      href={to}
      onClick={(e) => {
        e.preventDefault();
        startTransition(() => {
          navigate({ to });  // keeps current UI visible while next route loads
        });
      }}
      aria-busy={isPending}
    >
      {children}
      {isPending && <Spinner size="xs" />}
    </a>
  );
}
```

---

## 8. Error monitoring with Sentry

### React integration

```typescript
// main.tsx
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,

  integrations: [
    // Browser tracing for performance monitoring
    Sentry.browserTracingIntegration(),

    // React Router integration — tracks navigation as transactions
    // For TanStack Router, use the generic BrowserTracing and instrument manually
  ],

  tracesSampleRate: 0.1,  // 10% of transactions for performance monitoring

  // Correlate with Django's Sentry tracing via sentry-trace / baggage headers
  tracePropagationTargets: [/^\/api\//, /^https:\/\/api\.myapp\.com/],
});

const root = createRoot(document.getElementById("root")!, {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
});
```

### Sentry ErrorBoundary

Sentry's own ErrorBoundary reports errors automatically:

```typescript
import { ErrorBoundary } from "@sentry/react";

function App() {
  return (
    <ErrorBoundary
      fallback={({ error, resetError }) => (
        <ErrorFallback error={error} onReset={resetError} />
      )}
      showDialog  // shows Sentry's user feedback dialog on error
    >
      <MainContent />
    </ErrorBoundary>
  );
}
```

### Correlating with Django

When Sentry is configured in both Django and React with the same DSN and `tracePropagationTargets` includes the API URL, Sentry automatically propagates trace headers (`sentry-trace`, `baggage`) through Axios requests to Django. This links frontend and backend Sentry events into a single distributed trace.

### Manual error capture for expected errors

```typescript
import * as Sentry from "@sentry/react";

// In mutation error handlers or catch blocks:
onError: (error, variables) => {
  Sentry.captureException(error, {
    tags: { operation: "create-project" },
    extra: { input: variables },
  });
},
```

---

## 9. User-facing error UX

### Error strategy hierarchy

| Error type | UX pattern |
|---|---|
| Page-level load failure | Full error page with retry and/or back button |
| Data region failure | Inline error within the card/section with retry |
| Form submission failure | Inline field errors (from react-hook-form) or banner error |
| Network offline | Toast or persistent banner with reconnect detection |
| Unexpected JS error | Error boundary fallback with error ID for support |

### Retry with TanStack Query

When an ErrorBoundary wraps a Suspense+Query component, the "retry" button should invalidate the query:

```typescript
function DataRegionError({
  error,
  resetErrorBoundary,
}: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  const queryClient = useQueryClient();

  const handleRetry = () => {
    // Remove the failed query from cache so it re-fetches
    queryClient.removeQueries({ queryKey: ["relevant-key"] });
    resetErrorBoundary();
  };

  return (
    <div role="alert">
      <Text>Failed to load data</Text>
      <Button onClick={handleRetry}>Retry</Button>
    </div>
  );
}
```

### Error IDs for support correlated with Sentry

```typescript
function ErrorFallback({ error }: { error: Error }) {
  // Sentry assigns an event ID — user can quote this to support
  const eventId = Sentry.lastEventId();

  return (
    <div role="alert">
      <Heading>Something went wrong</Heading>
      <Text>Our team has been notified. Please try again.</Text>
      {eventId && (
        <Text fontSize="sm" color="gray.500">
          Error ID: {eventId}
        </Text>
      )}
      <Button onClick={() => window.location.reload()}>Reload</Button>
    </div>
  );
}
```
