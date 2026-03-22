---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - typescript-react-patterns.md
  - tanstack-query.md
  - react-hook-form-zod.md
  - tanstack-router.md
---

# Testing React: Vitest, RTL, and MSW

This stack — Vitest + React Testing Library (RTL) + Mock Service Worker (MSW) — is the default for Vite-based React apps. Vitest reuses the Vite pipeline (same transforms, same aliases, same module graph), RTL tests components from a user perspective, and MSW intercepts network at the service-worker or Node.js level.

---

## 1. Vitest configuration

### vite.config.ts

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
  test: {
    // Use jsdom to simulate a browser environment
    environment: "jsdom",
    
    // Runs before each test file — import global test setup
    setupFiles: ["./src/test/setup.ts"],
    
    // Makes describe/it/expect etc. available globally (like Jest)
    globals: true,
    
    // Optional: exclude files that aren't tests
    exclude: ["**/node_modules/**", "**/dist/**"],
    
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "html"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
    },
  },
});
```

If using `globals: true`, add `"vitest/globals"` to `compilerOptions.types` in tsconfig.json so TypeScript recognizes the global APIs without imports.

### src/test/setup.ts

```typescript
import "@testing-library/jest-dom";  // extends expect with .toBeInTheDocument() etc.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL cleanup after each test (unmounts components, clears DOM)
afterEach(() => {
  cleanup();
});
```

---

## 2. Vitest API

### Mocking functions

```typescript
import { vi, expect } from "vitest";

// Standalone mock function
const mockCallback = vi.fn();
mockCallback("hello");
expect(mockCallback).toHaveBeenCalledWith("hello");
expect(mockCallback).toHaveBeenCalledTimes(1);

// Mock with implementation
const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: () => ({ id: "1" }) });

// Spy on existing method without replacing it
const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
// After test:
consoleSpy.mockRestore();

// Module mocking — must be at top level (hoisted by vitest)
vi.mock("../api/users", () => ({
  fetchUser: vi.fn().mockResolvedValue({ id: "1", email: "test@example.com" }),
}));

// Clear all mocks between tests
afterEach(() => {
  vi.clearAllMocks();
});
```

### Fake timers

```typescript
describe("debounced search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("waits 300ms before firing", () => {
    const mockSearch = vi.fn();
    render(<SearchInput onSearch={mockSearch} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "react" } });
    
    expect(mockSearch).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(mockSearch).toHaveBeenCalledWith("react");
  });
});
```

### Running tests

```bash
npx vitest             # watch mode (default in dev)
npx vitest run         # single run (for CI)
npx vitest --coverage  # with coverage report
npx vitest run --reporter=verbose
```

---

## 3. React Testing Library

### The testing philosophy

RTL encourages tests that mirror how users interact with the app: find elements by accessible role, label, or text — not by CSS class or component name. This keeps tests robust to refactoring.

### Query priority (use in this order)

1. `getByRole` — the most semantic; finds by ARIA role + optional name
2. `getByLabelText` — for form inputs linked to a `<label>`
3. `getByPlaceholderText` — for inputs with placeholder (less accessible, lower priority)
4. `getByText` — for visible text content
5. `getByDisplayValue` — for the current value of input/select/textarea
6. `getByAltText` — for images
7. `getByTitle` — for title attribute
8. `getByTestId` — escape hatch only; add `data-testid` when no semantic query works

```typescript
// ✅ Preferred — semantic
screen.getByRole("button", { name: /submit/i });
screen.getByRole("textbox", { name: /email/i });
screen.getByRole("heading", { name: /welcome/i, level: 1 });
screen.getByLabelText("Password");

// ⚠️ Acceptable fallback
screen.getByText("Sign in");

// ❌ Avoid as first resort
screen.getByTestId("submit-button");
```

### Sync queries vs. async

```typescript
// getBy* — throws immediately if not found (use when element should be present)
screen.getByRole("button");

// queryBy* — returns null if not found (use to assert absence)
expect(screen.queryByRole("alert")).not.toBeInTheDocument();

// findBy* — async, polls until found or timeout (use when element appears after state change)
const toast = await screen.findByRole("status");

// waitFor — run assertion repeatedly until it passes
await waitFor(() => {
  expect(screen.getByRole("status")).toHaveTextContent("Saved");
});
```

### userEvent (v14 — async API)

`@testing-library/user-event` v14 simulates real browser events, including keyboard focus, selection, and bubbling. All interactions are async.

```typescript
import userEvent from "@testing-library/user-event";

it("fills out and submits a form", async () => {
  const user = userEvent.setup();  // creates an isolated user session
  const handleSubmit = vi.fn();
  
  render(<LoginForm onSubmit={handleSubmit} />);
  
  await user.type(screen.getByLabelText("Email"), "user@example.com");
  await user.type(screen.getByLabelText("Password"), "secret123");
  await user.click(screen.getByRole("button", { name: /sign in/i }));
  
  await waitFor(() => {
    expect(handleSubmit).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "secret123",
    });
  });
});
```

### within — scoped queries

When the same text appears in multiple places, scope the query to a container:

```typescript
const sidebar = screen.getByRole("navigation");
const mainContent = screen.getByRole("main");

// Find "Settings" link within the sidebar specifically
const sidebarSettings = within(sidebar).getByRole("link", { name: /settings/i });
```

### renderHook

For testing custom hooks in isolation:

```typescript
import { renderHook, act } from "@testing-library/react";

it("useCounter increments correctly", () => {
  const { result } = renderHook(() => useCounter());
  
  act(() => {
    result.current.increment();
  });
  
  expect(result.current.count).toBe(1);
});
```

---

## 4. Chakra UI testing pitfalls

### ChakraProvider in tests

Every component using Chakra hooks (`useColorMode`, `useTheme`, etc.) requires a `ChakraProvider` in the tree. Wrap renders globally via a custom render helper:

```typescript
// src/test/test-utils.tsx
import { render, RenderOptions } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { system } from "@/theme";  // your custom system config

function AllProviders({ children }: { children: React.ReactNode }) {
  return <ChakraProvider value={system}>{children}</ChakraProvider>;
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// Re-export everything so tests only import from this file
export * from "@testing-library/react";
```

### Portals (modals, menus, tooltips)

Chakra modals, drawers, menus, and tooltips render into portals — they're attached to `document.body`, not to the container returned by `render()`. This means:

```typescript
// ❌ Won't find the modal — it rendered into a portal outside the container
const { getByRole } = render(<MyModal isOpen />);
getByRole("dialog");  // fails

// ✅ screen always searches the full document including portals
screen.getByRole("dialog");
screen.getByRole("menu");
```

Always prefer `screen.*` over the destructured queries from `render()` when working with Chakra.

### Toasts

Chakra toasts render in a portal separate from your component. Access them via `screen.getByRole`:

```typescript
// Toasts have role="status" or role="alert" depending on status type
await screen.findByRole("status");  // success/info
await screen.findByRole("alert");   // error/warning
```

---

## 5. Mock Service Worker (MSW v2)

MSW intercepts network requests to HTTP handlers. In tests, it runs in Node.js mode. In dev/browser, it uses a service worker.

### Setup

```typescript
// src/test/handlers.ts — default handlers for happy-path scenarios
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/users/", () => {
    return HttpResponse.json([
      { id: "1", email: "alice@example.com", firstName: "Alice" },
      { id: "2", email: "bob@example.com", firstName: "Bob" },
    ]);
  }),
  
  http.get("/api/users/:id/", ({ params }) => {
    return HttpResponse.json({ id: params.id, email: "user@example.com" });
  }),
  
  http.post("/api/users/", async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: "3", ...body }, { status: 201 });
  }),
];
```

```typescript
// src/test/server.ts — node server instance
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

```typescript
// src/test/setup.ts (add to existing setup file)
import { server } from "./server";
import { beforeAll, afterAll, afterEach } from "vitest";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });  // fail fast on unmocked requests
});

afterEach(() => {
  server.resetHandlers();  // clear per-test overrides
});

afterAll(() => {
  server.close();
});
```

### Per-test overrides

```typescript
it("shows an error when the request fails", async () => {
  // Override the default handler for this test only
  server.use(
    http.get("/api/users/", () => {
      return HttpResponse.json({ detail: "Server error" }, { status: 500 });
    })
  );
  
  render(<UserList />);
  
  await screen.findByRole("alert");
  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
});
```

### Network errors

```typescript
import { http, HttpResponse } from "msw";

server.use(
  http.get("/api/users/", () => {
    return HttpResponse.error();  // Simulates network failure (fetch throws)
  })
);
```

### Inspecting requests

```typescript
it("sends correct payload on create", async () => {
  let capturedBody: unknown;
  
  server.use(
    http.post("/api/projects/", async ({ request }) => {
      capturedBody = await request.json();
      return HttpResponse.json({ id: "new-id" }, { status: 201 });
    })
  );
  
  const user = userEvent.setup();
  render(<CreateProjectForm />);
  await user.type(screen.getByLabelText("Name"), "My Project");
  await user.click(screen.getByRole("button", { name: /create/i }));
  
  await waitFor(() => {
    expect(capturedBody).toEqual({ name: "My Project", isPublic: false });
  });
});
```

---

## 6. Testing TanStack Query

### Wrapper setup

Each test needs a fresh `QueryClient` to avoid cache leaking between tests:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,        // don't retry on error in tests
        staleTime: Infinity, // don't refetch during test
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    ),
    queryClient,
  };
}
```

### Add to global test wrapper

Compose with the Chakra wrapper:

```typescript
function AllProviders({ children }: { children: React.ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={system}>{children}</ChakraProvider>
    </QueryClientProvider>
  );
}
```

Note: using a singleton `queryClient` inside `AllProviders` means cache isn't isolated per test. For isolated tests, pass a fresh client via the `renderWithQuery` pattern instead.

### Testing data loading states

```typescript
it("shows loading spinner, then user list", async () => {
  // MSW default handler returns the user list
  render(<UserList />, { wrapper: AllProviders });
  
  // Loading state
  expect(screen.getByRole("progressbar")).toBeInTheDocument();
  
  // Data loaded
  const items = await screen.findAllByRole("listitem");
  expect(items).toHaveLength(2);
});
```

### renderHook with TanStack Query

```typescript
it("useUsers returns parsed data", async () => {
  const { result } = renderHook(() => useUsers(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={createTestQueryClient()}>
        {children}
      </QueryClientProvider>
    ),
  });
  
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toHaveLength(2);
});
```

---

## 7. Testing react-hook-form

Because RHF is uncontrolled by default, use `userEvent` (not `fireEvent`) to trigger real DOM events:

```typescript
it("validates required fields", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  
  render(<LoginForm onSubmit={onSubmit} />);
  
  // Submit without filling fields
  await user.click(screen.getByRole("button", { name: /sign in/i }));
  
  // Validation messages appear
  expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
  expect(screen.getByText(/password is required/i)).toBeInTheDocument();
  expect(onSubmit).not.toHaveBeenCalled();
});

it("submits valid data", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  
  render(<LoginForm onSubmit={onSubmit} />);
  
  await user.type(screen.getByLabelText(/email/i), "alice@example.com");
  await user.type(screen.getByLabelText(/password/i), "securepassword");
  await user.click(screen.getByRole("button", { name: /sign in/i }));
  
  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({
      email: "alice@example.com",
      password: "securepassword",
    });
  });
});
```

---

## 8. Testing routing (TanStack Router)

```typescript
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";

function renderWithRouter(initialPath = "/") {
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  
  return {
    ...render(<RouterProvider router={router} />),
    router,
  };
}

it("redirects unauthenticated users to /login", async () => {
  renderWithRouter("/dashboard");
  
  await waitFor(() => {
    expect(window.location.pathname).toBe("/login");
  });
});

it("renders the dashboard when authenticated", async () => {
  // Pre-populate auth in MockAuthProvider or MSW /api/me/ handler
  server.use(
    http.get("/api/me/", () => HttpResponse.json({ id: "1", email: "user@example.com" }))
  );
  
  renderWithRouter("/dashboard");
  
  await screen.findByRole("heading", { name: /dashboard/i });
});
```

---

## 9. Snapshot testing discipline

Snapshot tests catch unintended visual regressions but become a maintenance burden if overused.

- **Use sparingly** — prefer behavioral assertions (element presence, text content) over full component snapshots
- **Snapshot what matters** — a specific output value or serialized config, not an entire component tree
- **Inline snapshots** (in code) are more readable than `.snap` files for small outputs
- **Update intentionally** — always review snapshot diffs before updating

```typescript
// ✅ Focused inline snapshot of a configuration value
it("generates the correct chart config", () => {
  const config = buildChartConfig(data);
  expect(config.title).toMatchInlineSnapshot(`"Monthly Revenue"`);
  expect(config.series).toHaveLength(3);
});

// ❌ Avoid — brittle full component snapshot
it("renders UserCard", () => {
  const { container } = render(<UserCard user={mockUser} />);
  expect(container).toMatchSnapshot();  // fails on any markup change
});
```
