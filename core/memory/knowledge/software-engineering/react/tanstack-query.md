---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [react, tanstack-query, data-fetching, drf, server-state]
version_note: TanStack Query v5 (React 18 required). Several v4→v5 breaking changes are called out throughout.
related:
  - tanstack-router.md
  - ../../ai/frontier/retrieval-memory/hyde-query-expansion.md
  - react-error-boundaries-suspense.md
  - ../web-fundamentals/api-design-patterns.md
---

# TanStack Query v5 — Server State for DRF-backed React UIs

## Why TanStack Query

A DRF API returns data that lives on the server. Without a dedicated library, every component ends up with its own `useEffect + fetch + useState(loading/error/data)` pattern, with no sharing, no background refresh, and no cache. TanStack Query replaces that with a global, keyed, stale-while-revalidate cache that handles loading/error states, deduplication, refetching, and mutations in a consistent way.

```bash
npm install @tanstack/react-query
npm install @tanstack/react-query-devtools   # development only
```

---

## Core setup

```tsx
// main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,      // 1 minute — data is fresh for this long
      gcTime: 1000 * 60 * 10,    // 10 minutes — cache kept after last observer unmounts
      retry: 1,                  // retry once on failure (default is 3)
      refetchOnWindowFocus: true,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

**v5 note**: `cacheTime` was renamed to `gcTime`. The default `staleTime` is 0 (always stale). For a DRF API, setting a modest global `staleTime` (e.g. 60s) avoids waterfalls without stale data concerns.

---

## Query keys

Query keys identify cached data. They must be serializable (arrays of primitives/objects):

```ts
// keys.ts — centralize keys to avoid typos and enable targeted invalidation
export const articleKeys = {
  all: ['articles'] as const,
  lists: () => [...articleKeys.all, 'list'] as const,
  list: (filters: ArticleFilters) => [...articleKeys.lists(), filters] as const,
  details: () => [...articleKeys.all, 'detail'] as const,
  detail: (id: number) => [...articleKeys.details(), id] as const,
}
```

Key factories like this let you invalidate at any level of specificity:

```ts
// Invalidate all article queries
queryClient.invalidateQueries({ queryKey: articleKeys.all })
// Invalidate only the list queries
queryClient.invalidateQueries({ queryKey: articleKeys.lists() })
// Invalidate one detail
queryClient.invalidateQueries({ queryKey: articleKeys.detail(id) })
```

---

## useQuery — fetching data

```tsx
import { useQuery } from '@tanstack/react-query'
import { fetchArticle } from '../api/articles'

function ArticleDetail({ id }: { id: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: articleKeys.detail(id),
    queryFn: () => fetchArticle(id),
  })

  if (isPending) return <Spinner />
  if (isError) return <ErrorMessage error={error} />
  return <Article article={data} />
}
```

### Status terminology (v5)

| Flag | Meaning |
|---|---|
| `isPending` | No data in cache yet (replaces v4's `isLoading`) |
| `isFetching` | A network request is in flight (including background refetches) |
| `isLoading` | `isPending && isFetching` — the initial hard loading state |
| `isSuccess` | Data is available |
| `isError` | Last fetch failed and no cached data |

**v5 breaking change**: `isLoading` used to mean "no data yet"; it now means "no data AND currently fetching". Use `isPending` for "no cached data yet".

### Conditional queries with `enabled`

```tsx
// Only fetch when userId is available
const { data: profile } = useQuery({
  queryKey: ['profile', userId],
  queryFn: () => fetchProfile(userId!),
  enabled: !!userId,
})

// Dependent query — second depends on first
const { data: user } = useQuery({ queryKey: ['user', id], queryFn: () => fetchUser(id) })
const { data: projects } = useQuery({
  queryKey: ['projects', user?.orgId],
  queryFn: () => fetchProjects(user!.orgId),
  enabled: !!user?.orgId,
})
```

---

## Fetching from DRF with axios

```ts
// api/client.ts
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
  withCredentials: true,          // send cookies (for session auth)
  headers: { 'Content-Type': 'application/json' },
})

// Read CSRF token from cookie for mutations
function getCsrfToken(): string {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1] ?? ''
}

// Attach CSRF to every mutating request
apiClient.interceptors.request.use(config => {
  if (['post', 'put', 'patch', 'delete'].includes(config.method ?? '')) {
    config.headers['X-CSRFToken'] = getCsrfToken()
  }
  return config
})
```

```ts
// api/articles.ts
import { apiClient } from './client'
import type { Article, ArticleFilters } from '../types'

export const fetchArticles = async (filters: ArticleFilters) => {
  const { data } = await apiClient.get<DRFListResponse<Article>>('/articles/', { params: filters })
  return data
}

export const fetchArticle = async (id: number) => {
  const { data } = await apiClient.get<Article>(`/articles/${id}/`)
  return data
}
```

---

## DRF pagination with useQuery

DRF's cursor paginator returns `{ count, next, previous, results }`. Keep previous data visible while the new page loads:

```tsx
import { keepPreviousData } from '@tanstack/react-query'

function ArticleList({ page }: { page: number }) {
  const { data, isPending, isFetching } = useQuery({
    queryKey: articleKeys.list({ page }),
    queryFn: () => fetchArticles({ page }),
    placeholderData: keepPreviousData,   // v5: was keepPreviousData: true in v4
  })

  return (
    <>
      {isFetching && <LoadingBadge />}   {/* background fetch indicator */}
      <ArticleGrid articles={data?.results ?? []} />
      <Pagination count={data?.count} page={page} />
    </>
  )
}
```

**v5 breaking change**: `keepPreviousData: true` is gone. Import `keepPreviousData` from `@tanstack/react-query` and pass it as `placeholderData: keepPreviousData`.

---

## useMutation — writing data

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'

function PublishButton({ article }: { article: Article }) {
  const queryClient = useQueryClient()

  const { mutate, isPending } = useMutation({
    mutationFn: (id: number) => apiClient.post(`/articles/${id}/publish/`),
    onSuccess: (_, id) => {
      // Invalidate the detail and the list so both refetch
      queryClient.invalidateQueries({ queryKey: articleKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() })
    },
    onError: (error) => {
      toast.error('Failed to publish: ' + getErrorMessage(error))
    },
  })

  return (
    <Button onClick={() => mutate(article.id)} isLoading={isPending}>
      Publish
    </Button>
  )
}
```

**v5 note**: `onSuccess` / `onError` / `onSettled` callbacks are still valid on `useMutation` (they were removed from `useQuery` in v5).

---

## Optimistic updates

Optimistic updates make the UI respond instantly before the server confirms, then roll back on error:

```tsx
const { mutate } = useMutation({
  mutationFn: ({ id, liked }: { id: number; liked: boolean }) =>
    apiClient.patch(`/articles/${id}/`, { liked }),

  onMutate: async ({ id, liked }) => {
    // 1. Cancel any in-flight refetches to avoid overwriting optimistic data
    await queryClient.cancelQueries({ queryKey: articleKeys.detail(id) })

    // 2. Snapshot the current value for rollback
    const previous = queryClient.getQueryData<Article>(articleKeys.detail(id))

    // 3. Apply the optimistic update
    queryClient.setQueryData<Article>(articleKeys.detail(id), old =>
      old ? { ...old, liked } : old
    )

    return { previous }  // context passed to onError
  },

  onError: (_error, { id }, context) => {
    // 4. Roll back to the snapshot on failure
    if (context?.previous) {
      queryClient.setQueryData(articleKeys.detail(id), context.previous)
    }
  },

  onSettled: (_data, _error, { id }) => {
    // 5. Always refetch after settle to ensure cache matches server
    queryClient.invalidateQueries({ queryKey: articleKeys.detail(id) })
  },
})
```

The pattern: cancel → snapshot → apply → rollback on error → invalidate on settle.

---

## Prefetching — TanStack Router integration

In a TanStack Router setup, prefetch in route loaders before the component renders:

```ts
// routes/articles/$id.tsx
import { createRoute } from '@tanstack/react-router'
import { articleKeys, fetchArticle } from '../api/articles'

export const articleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/articles/$id',
  loader: async ({ context: { queryClient }, params: { id } }) => {
    // Ensure data is in cache before the component renders
    await queryClient.ensureQueryData({
      queryKey: articleKeys.detail(Number(id)),
      queryFn: () => fetchArticle(Number(id)),
    })
  },
})
```

```tsx
// The component never sees a loading state — data is already there
function ArticleDetail() {
  const { id } = useParams({ from: articleRoute.id })
  const { data } = useQuery({
    queryKey: articleKeys.detail(Number(id)),
    queryFn: () => fetchArticle(Number(id)),
  })
  // data is always defined here because the loader pre-populated the cache
  return <Article article={data!} />
}
```

For non-Router prefetching (hover, anticipate next page):

```ts
queryClient.prefetchQuery({
  queryKey: articleKeys.detail(nextId),
  queryFn: () => fetchArticle(nextId),
  staleTime: 10_000,   // don't prefetch if already fresh
})
```

---

## useInfiniteQuery — infinite scroll

```tsx
import { useInfiniteQuery } from '@tanstack/react-query'

function InfiniteArticleList() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: articleKeys.lists(),
    queryFn: ({ pageParam }) => fetchArticles({ cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next
      ? new URL(lastPage.next).searchParams.get('cursor') ?? undefined
      : undefined,
  })

  const articles = data?.pages.flatMap(page => page.results) ?? []

  return (
    <>
      {articles.map(a => <ArticleCard key={a.id} article={a} />)}
      {hasNextPage && (
        <Button onClick={() => fetchNextPage()} isLoading={isFetchingNextPage}>
          Load more
        </Button>
      )}
    </>
  )
}
```

**v5 note**: `initialPageParam` is now required. `getNextPageParam` returning `undefined` signals no more pages.

---

## useSuspenseQuery — Suspense integration

v5 has dedicated Suspense hooks. Data is always defined when the component renders; loading is handled by a `<Suspense>` boundary above, errors by an `<ErrorBoundary>`:

```tsx
import { useSuspenseQuery } from '@tanstack/react-query'

function ArticleDetail({ id }: { id: number }) {
  // data is always Article — no isPending/isError to check
  const { data } = useSuspenseQuery({
    queryKey: articleKeys.detail(id),
    queryFn: () => fetchArticle(id),
  })
  return <Article article={data} />
}

// Parent
function ArticlePage({ id }: { id: number }) {
  return (
    <ErrorBoundary fallback={<ErrorFallback />}>
      <Suspense fallback={<ArticleSkeleton />}>
        <ArticleDetail id={id} />
      </Suspense>
    </ErrorBoundary>
  )
}
```

**v5 notes**:
- `suspense: true` option on `useQuery` is removed. Use `useSuspenseQuery` explicitly.
- `enabled` is not available on `useSuspenseQuery` — if you need conditional fetching, use `useQuery` instead.
- `throwOnError` cannot be overridden on `useSuspenseQuery`.

---

## Global error handling — 401 redirect

```ts
// api/client.ts
apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Clear query cache and redirect to login
      queryClient.clear()
      window.location.href = `/login?from=${encodeURIComponent(window.location.pathname)}`
    }
    return Promise.reject(error)
  }
)
```

For a more React-idiomatic approach, combine with `useQueryErrorResetBoundary`:

```tsx
import { useQueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'

function QueryErrorBoundary({ children }: { children: React.ReactNode }) {
  const { reset } = useQueryErrorResetBoundary()
  return (
    <ErrorBoundary
      onReset={reset}
      fallbackRender={({ resetErrorBoundary }) => (
        <div>
          <p>Something went wrong.</p>
          <button onClick={resetErrorBoundary}>Try again</button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  )
}
```

---

## useQueries — parallel queries with aggregation

```tsx
import { useQueries } from '@tanstack/react-query'

function MultiArticleView({ ids }: { ids: number[] }) {
  const results = useQueries({
    queries: ids.map(id => ({
      queryKey: articleKeys.detail(id),
      queryFn: () => fetchArticle(id),
    })),
    // v5: combine lets you transform the array of results
    combine: (results) => ({
      articles: results.map(r => r.data).filter(Boolean),
      isPending: results.some(r => r.isPending),
    }),
  })

  if (results.isPending) return <Spinner />
  return <ArticleGrid articles={results.articles} />
}
```

---

## DevTools

```tsx
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

// Add inside QueryClientProvider, anywhere in the tree
<ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
```

The DevTools panel shows all active queries, their cache status, data, and lets you trigger refetches and invalidations manually. Essential during development.

---

## Common DRF-specific patterns

### Handling DRF field errors on mutations

```tsx
const { mutate } = useMutation({
  mutationFn: (data: ArticleInput) => apiClient.post('/articles/', data),
  onError: (error: AxiosError<DRFValidationError>) => {
    // DRF returns { field_name: ["Error message."], non_field_errors: [...] }
    const fieldErrors = error.response?.data
    if (fieldErrors && form) {
      Object.entries(fieldErrors).forEach(([field, messages]) => {
        form.setError(field as keyof ArticleInput, {
          message: (messages as string[]).join(' '),
        })
      })
    }
  },
})
```

### CSRF token for session-auth mutations

Already handled by the axios interceptor shown above. With JWT auth instead, set the token in the Authorization header:

```ts
apiClient.interceptors.request.use(config => {
  const token = getAccessToken() // from memory / cookie
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

---

## Quick reference

| Scenario | Hook |
|---|---|
| Fetch data, show loading/error | `useQuery` |
| Fetch data, Suspense boundary above | `useSuspenseQuery` |
| Infinite scroll / paginated list | `useInfiniteQuery` |
| Multiple parallel queries | `useQueries` |
| Create / update / delete | `useMutation` |
| Prefetch before render | `queryClient.prefetchQuery` |
| Ensure in cache (throws if missing) | `queryClient.ensureQueryData` |
| Cache write without network | `queryClient.setQueryData` |
| Force refetch | `queryClient.invalidateQueries` |
