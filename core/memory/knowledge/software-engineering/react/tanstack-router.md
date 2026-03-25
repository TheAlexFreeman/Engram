---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [react, routing, tanstack-router, typescript, spa]
version_note: TanStack Router v1 (stable). Vite plugin is now @tanstack/router-plugin/vite.
related:
  - tanstack-query.md
  - react-error-boundaries-suspense.md
  - react-hook-form-zod.md
---

# TanStack Router v1 — Type-Safe Routing for React SPAs

## Why TanStack Router over React Router

TanStack Router provides end-to-end TypeScript type safety that React Router (v6/v7) cannot match:

- **Route params**: `useParams()` returns correctly typed values — no casting
- **Search params**: first-class schema-validated state with `validateSearch` (zod); React Router's `useSearchParams` returns raw strings
- **Loader data**: `useLoaderData()` is typed to the exact shape the loader returns
- **`Link` component**: `to` prop is type-checked against the full route tree — invalid paths are a TypeScript error at build time
- **Navigation**: `navigate({ to: '/articles/$id', params: { id } })` is fully typed

The tradeoff is more upfront configuration than React Router. It pays off quickly on any app with meaningful URL state (filters, pagination, tabs as search params).

---

## Installation

```bash
npm install @tanstack/react-router
npm install --save-dev @tanstack/router-plugin    # Vite plugin for file-based routing
npm install @tanstack/router-devtools             # dev only
```

---

## Two setup approaches: file-based vs code-based

### File-based (recommended for new projects)

The Vite plugin watches your `src/routes/` directory and auto-generates a type-safe route tree in `src/routeTree.gen.ts`. You never edit `routeTree.gen.ts` by hand.

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'

export default defineConfig({
  plugins: [
    TanStackRouterVite(),   // must come before plugin-react
    react(),
  ],
})
```

Typical `src/routes/` structure:

```
src/routes/
├── __root.tsx          # Root layout (wraps everything)
├── index.tsx           # /
├── articles/
│   ├── index.tsx       # /articles
│   ├── $id.tsx         # /articles/$id
│   └── new.tsx         # /articles/new
├── settings.tsx        # /settings
└── _auth/              # Pathless layout route (auth guard)
    ├── dashboard.tsx   # /dashboard (but rendered inside _auth layout)
    └── profile.tsx     # /profile
```

Convention: `_` prefix = pathless layout route (adds layout/guards without adding a URL segment). `$` prefix = dynamic param segment.

### Code-based (useful for programmatic or complex route trees)

```ts
// src/router.ts
import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { RootLayout } from './layouts/RootLayout'
import { ArticleList } from './pages/ArticleList'
import { ArticleDetail } from './pages/ArticleDetail'

const rootRoute = createRootRoute({ component: RootLayout })

const articlesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/articles',
  component: ArticleList,
})

const articleDetailRoute = createRoute({
  getParentRoute: () => articlesRoute,
  path: '$id',
  component: ArticleDetail,
})

const routeTree = rootRoute.addChildren([
  articlesRoute.addChildren([articleDetailRoute]),
])

export const router = createRouter({ routeTree })

// TypeScript: register the router type globally so all hooks are typed
declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
```

```tsx
// main.tsx
import { RouterProvider } from '@tanstack/react-router'
import { router } from './router'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
  </QueryClientProvider>
)
```

---

## Root layout — `__root.tsx`

The root route wraps the entire app. Put providers, nav, and the `<Outlet />` here:

```tsx
// src/routes/__root.tsx
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/router-devtools'
import type { QueryClient } from '@tanstack/react-query'

// createRootRouteWithContext injects context into every loader
interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <>
      <Nav />
      <Outlet />
      <TanStackRouterDevtools />
    </>
  ),
})
```

Pass context when creating the router:

```ts
export const router = createRouter({
  routeTree,
  context: { queryClient },
})
```

---

## Type safety model

Once the router is registered (the `declare module` block above), every TanStack Router hook is fully typed from the route tree. No generic arguments or casts needed:

```tsx
// Inside /articles/$id route component
import { useParams, useLoaderData, useSearch } from '@tanstack/react-router'

const { id } = useParams({ from: '/articles/$id' })
// id: string — TypeScript knows this route has an $id param

const article = useLoaderData({ from: '/articles/$id' })
// article: Article — typed to what the loader returns

const { page, tag } = useSearch({ from: '/articles/' })
// page: number, tag: string — typed from the validateSearch schema
```

The `from` argument scopes the hook to a specific route, giving the precise types for that route. Omitting `from` gives a union of all possible types (less useful).

---

## Loaders — data before render

Loaders run before the component renders, so the component never sees a loading state for its primary data:

```tsx
// src/routes/articles/$id.tsx
import { createFileRoute } from '@tanstack/react-router'
import { articleKeys, fetchArticle } from '../../api/articles'

export const Route = createFileRoute('/articles/$id')({
  loader: async ({ context: { queryClient }, params: { id } }) => {
    // ensureQueryData: returns cached data if fresh, otherwise fetches
    return queryClient.ensureQueryData({
      queryKey: articleKeys.detail(Number(id)),
      queryFn: () => fetchArticle(Number(id)),
    })
  },
  component: ArticleDetail,
})

function ArticleDetail() {
  // loaderData is the return value of loader — typed automatically
  const article = Route.useLoaderData()
  return <Article article={article} />
}
```

### loaderDeps — search-param-dependent loaders

When your loader depends on search params (e.g., filters, page number), declare the dependency explicitly so TanStack Router knows to re-run the loader when those params change:

```tsx
export const Route = createFileRoute('/articles/')({
  validateSearch: z.object({
    page: z.number().int().min(1).default(1),
    tag: z.string().optional(),
  }),
  loaderDeps: ({ search: { page, tag } }) => ({ page, tag }),
  loader: async ({ context: { queryClient }, deps: { page, tag } }) => {
    return queryClient.ensureQueryData({
      queryKey: articleKeys.list({ page, tag }),
      queryFn: () => fetchArticles({ page, tag }),
    })
  },
  component: ArticleList,
})
```

### staleTime on loaders

Avoid refetching when navigating back to a route that was recently loaded:

```tsx
export const Route = createFileRoute('/articles/$id')({
  loader: ({ context: { queryClient }, params: { id } }) =>
    queryClient.ensureQueryData({ queryKey: articleKeys.detail(Number(id)), queryFn: () => fetchArticle(Number(id)) }),
  staleTime: 10_000,   // don't re-run the loader if data is less than 10s old
})
```

---

## Search params as first-class state

This is one of TanStack Router's biggest advantages. Search params are schema-validated, typed, and serialized/deserialized automatically.

```tsx
import { z } from 'zod'

export const Route = createFileRoute('/articles/')({
  validateSearch: z.object({
    page: z.number().int().min(1).catch(1),      // .catch() sets default on parse failure
    tag: z.string().optional(),
    sort: z.enum(['newest', 'oldest', 'popular']).catch('newest'),
    q: z.string().optional(),
  }),
  component: ArticleList,
})

function ArticleList() {
  const { page, tag, sort, q } = Route.useSearch()
  // All typed: page is number, sort is 'newest'|'oldest'|'popular', etc.

  return (
    <>
      <SearchInput defaultValue={q} />
      <SortSelect value={sort} />
      <ArticleGrid articles={...} />
    </>
  )
}
```

### Updating search params — navigate and Link

```tsx
import { useNavigate, Link } from '@tanstack/react-router'

function Pagination({ totalPages }: { totalPages: number }) {
  const navigate = useNavigate({ from: '/articles/' })
  const { page } = Route.useSearch()

  return (
    <button onClick={() => navigate({ search: prev => ({ ...prev, page: page + 1 }) })}>
      Next
    </button>
  )
}

// Or with Link — also fully typed
<Link to="/articles/" search={{ page: 2, sort: 'newest' }}>
  Page 2
</Link>
```

The `search` updater function (`prev => ...`) is the safe pattern — it preserves existing params while updating specific ones.

---

## Nested routes and layouts

```tsx
// __root.tsx — wraps everything
export const Route = createRootRoute({ component: () => <><Nav /><Outlet /></> })

// src/routes/articles/index.tsx — /articles layout
export const Route = createFileRoute('/articles/')({
  component: () => (
    <div className="article-layout">
      <ArticleSidebar />
      <Outlet />      {/* child routes render here */}
    </div>
  ),
})

// src/routes/articles/$id.tsx — /articles/$id
export const Route = createFileRoute('/articles/$id')({
  component: ArticleDetail,
})
```

### Pathless layout routes (auth guards, common wrappers)

A directory or file prefixed with `_` adds a layout without contributing a URL segment:

```tsx
// src/routes/_authenticated.tsx — no URL contribution
export const Route = createFileRoute('/_authenticated')({
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) {
      throw redirect({ to: '/login', search: { from: location.pathname } })
    }
  },
  component: () => <Outlet />,   // just renders children
})

// src/routes/_authenticated/dashboard.tsx — URL is /dashboard (not /_authenticated/dashboard)
export const Route = createFileRoute('/_authenticated/dashboard')({
  component: Dashboard,
})
```

---

## Protected routes — beforeLoad

`beforeLoad` runs before the loader and before the component renders. Use it for auth guards:

```tsx
import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ context, location }) => {
    const { auth } = context
    if (!auth.isAuthenticated) {
      throw redirect({
        to: '/login',
        search: { from: location.href },   // preserve destination for post-login redirect
      })
    }
  },
})
```

Post-login redirect — consume the `from` param after successful login:

```tsx
function LoginPage() {
  const { from } = Route.useSearch()
  const navigate = useNavigate()

  const handleSuccess = () => {
    navigate({ to: from ?? '/dashboard', replace: true })
  }
}
```

### Role-based guards

```tsx
beforeLoad: ({ context }) => {
  if (!context.auth.roles.includes('admin')) {
    throw redirect({ to: '/403' })
  }
}
```

---

## Navigation

### Link component

```tsx
import { Link } from '@tanstack/react-router'

// Fully typed — TypeScript will error on invalid `to` paths
<Link to="/articles/$id" params={{ id: article.id }}>
  {article.title}
</Link>

// Active styling
<Link
  to="/articles"
  activeProps={{ className: 'nav-active' }}
  activeOptions={{ exact: true }}
>
  Articles
</Link>

// With search params
<Link to="/articles/" search={{ sort: 'newest', page: 1 }}>
  Newest articles
</Link>
```

### useNavigate — imperative navigation

```tsx
const navigate = useNavigate()

// Push to history
navigate({ to: '/articles/$id', params: { id: newId } })

// Replace (no history entry — good for post-form-submit redirects)
navigate({ to: '/articles', replace: true })

// Update only search params (stay on same route)
navigate({ search: prev => ({ ...prev, page: 2 }) })

// Go back
navigate({ to: '..', from: '/articles/$id' })
```

---

## Pending UI and transitions

TanStack Router shows `pendingComponent` when a loader takes longer than `pendingMs` milliseconds:

```tsx
export const Route = createFileRoute('/articles/$id')({
  loader: ({ context: { queryClient }, params: { id } }) =>
    queryClient.ensureQueryData({ ... }),
  pendingComponent: ArticleSkeleton,   // shown after pendingMs delay
  pendingMs: 200,                      // don't flash for fast loads
  pendingMinMs: 300,                   // if shown, keep visible at least this long
  component: ArticleDetail,
})
```

For navigation transitions (keep old UI visible while loading new route):

```tsx
import { useRouterState } from '@tanstack/react-router'

function Nav() {
  const isLoading = useRouterState({ select: s => s.isLoading })
  return (
    <nav className={isLoading ? 'nav-loading' : ''}>
      {/* ... */}
    </nav>
  )
}
```

---

## Error handling

Each route can define an `errorComponent` for route-scoped errors:

```tsx
import { createFileRoute, useRouter } from '@tanstack/react-router'
import { ErrorComponent } from '@tanstack/react-router'

export const Route = createFileRoute('/articles/$id')({
  loader: ({ params: { id } }) => fetchArticle(Number(id)),
  errorComponent: ({ error, reset }) => (
    <div>
      <p>Failed to load article: {error.message}</p>
      <button onClick={reset}>Retry</button>
    </div>
  ),
  component: ArticleDetail,
})
```

`reset()` re-runs the loader. The error boundary is scoped to the route, so the rest of the app remains functional.

For global errors, add `errorComponent` to the root route.

### NotFoundRoute

```tsx
const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  component: NotFoundPage,
})
```

Or in file-based routing, create `src/routes/$.tsx`.

---

## Code splitting — lazy routes

```tsx
// File-based: use Route.lazy() on the component
export const Route = createFileRoute('/articles/$id')({
  loader: ...,
  component: lazyRouteComponent(() => import('./ArticleDetail')),
})

// Code-based: createLazyFileRoute
// ArticleDetail.lazy.tsx
export const Route = createLazyFileRoute('/articles/$id')({
  component: ArticleDetail,
})
```

In file-based routing, the convention is to split the route file into two:
- `articles.$id.tsx` — the non-lazy parts (loader, search validation, `beforeLoad`)
- `articles.$id.lazy.tsx` — the component (lazy-loaded)

TanStack Router's Vite plugin handles the code splitting automatically when it detects `.lazy.tsx` files.

---

## TanStack Query integration — the full pattern

The natural pairing: Router handles routing and prefetching, Query handles caching and background sync.

```ts
// src/router.ts
import { createRouter } from '@tanstack/react-router'
import { routeTree } from './routeTree.gen'
import { queryClient } from './queryClient'

export const router = createRouter({
  routeTree,
  context: { queryClient },         // available in every loader
  defaultPreload: 'intent',         // prefetch on hover/focus
  defaultPreloadStaleTime: 0,       // always check freshness on preload
})
```

```tsx
// Route with loader + useQuery (belt-and-suspenders pattern)
export const Route = createFileRoute('/articles/$id')({
  loader: ({ context: { queryClient }, params: { id } }) =>
    queryClient.ensureQueryData({
      queryKey: articleKeys.detail(Number(id)),
      queryFn: () => fetchArticle(Number(id)),
    }),
  component: ArticleDetail,
})

function ArticleDetail() {
  const { id } = useParams({ from: '/articles/$id' })
  // useQuery reads from cache populated by the loader — no loading state
  const { data: article } = useQuery({
    queryKey: articleKeys.detail(Number(id)),
    queryFn: () => fetchArticle(Number(id)),
  })
  // article is Article (not undefined) because the loader ran first
  return <Article article={article!} />
}
```

`defaultPreload: 'intent'` makes TanStack Router run loaders when the user hovers over a `<Link>`, which translates to prefetching the Query cache before the user clicks.

---

## DevTools

```tsx
import { TanStackRouterDevtools } from '@tanstack/router-devtools'

// Add inside the root route component
export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <TanStackRouterDevtools position="bottom-right" />
    </>
  ),
})
```

Shows the full route tree, matched routes, loader states, and search param values. Invaluable for debugging loader/param issues.

---

## Common patterns and pitfalls

**Always use `search: prev => ...` when updating search params**
`navigate({ search: { page: 2 } })` resets all other params. The updater form `search: prev => ({ ...prev, page: 2 })` preserves them.

**Prefer `ensureQueryData` over `fetchQuery` in loaders**
`ensureQueryData` returns cached data if it's fresh; `fetchQuery` always makes a network call. The former is almost always what you want.

**`from` argument on hooks scopes the type**
`useParams({ from: '/articles/$id' })` returns `{ id: string }`. Without `from`, you get the union of all routes' params — less useful and requires narrowing.

**Don't put server-only data in search params**
Search params are visible in the URL and stored in browser history. Use them for UI state (filters, sort, page); use loader data for fetched server state.

**File-based route naming conventions**

| File | URL |
|---|---|
| `index.tsx` | `/` (exact) |
| `about.tsx` | `/about` |
| `articles/index.tsx` | `/articles` |
| `articles/$id.tsx` | `/articles/:id` |
| `articles/$id.edit.tsx` | `/articles/:id/edit` |
| `_auth.tsx` | pathless layout (no URL) |
| `$.tsx` | catch-all / not found |
