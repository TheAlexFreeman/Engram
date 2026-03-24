---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - tanstack-query.md
  - tanstack-router.md
  - react-19-overview.md
  - ../web-fundamentals/cors-in-depth.md
---

# React Authentication Patterns with Django/DRF

Authentication in a React SPA paired with Django REST Framework has several interlocking parts: where tokens live, how auth state flows through the component tree, how protected routes work, and how to handle tokens expiring mid-session. This file covers the recommended patterns for this stack.

---

## 1. Token storage comparison

| Strategy | XSS safe? | CSRF safe? | Survives refresh? | Recommendation |
|---|---|---|---|---|
| httpOnly cookie | ✅ yes | ⚠️ needs token | ✅ yes | **Recommended for DRF sessions/JWT** |
| localStorage | ❌ no | ✅ yes | ✅ yes | Avoid (XSS risk) |
| In-memory (React state) | ✅ yes | ✅ yes | ❌ lost on refresh | Use with silent refresh via cookie |
| sessionStorage | ❌ no (same origin) | ✅ yes | ❌ lost on tab close | Generally worse than alternatives |

### Why httpOnly cookies for DRF

With Django's session auth or `djangorestframework-simplejwt` configured to use cookies:
- The browser sends the cookie automatically — no code to read/attach it
- JavaScript cannot read the cookie (prevents XSS token theft)
- Django's `SessionMiddleware` or `JWTAuthentication` reads it on the server
- The only mitigation needed is CSRF (see section 7)

---

## 2. Auth state management

### Pattern: TanStack Query for /api/me/

The cleanest approach is treating the current user as a query, not separate state. This avoids a parallel auth store.

```typescript
// hooks/useCurrentUser.ts
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { UserSchema, type User } from "@/api/schemas";

export const currentUserQueryOptions = queryOptions({
  queryKey: ["me"],
  queryFn: async (): Promise<User> => {
    const res = await apiClient.get("/api/me/");
    return UserSchema.parse(res.data);
  },
  staleTime: 5 * 60 * 1000,    // don't refetch for 5 minutes
  retry: false,                  // 401 means logged out — don't retry
});

export function useCurrentUser() {
  return useQuery(currentUserQueryOptions);
}
```

### Auth context: thin wrapper over query

```typescript
// contexts/AuthContext.tsx
type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useCurrentUser();

  const value: AuthContextValue = {
    user: user ?? null,
    isAuthenticated: !!user,
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

This keeps auth state and server state in sync — invalidating the `["me"]` query from anywhere automatically updates the auth context.

---

## 3. Login and logout

### Login flow

```typescript
// hooks/useLogin.ts
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useLogin() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      apiClient.post("/api/auth/login/", credentials),

    onSuccess: async () => {
      // Refetch the /me query to populate auth state
      await queryClient.invalidateQueries({ queryKey: ["me"] });

      // Read redirect destination from URL (set by protected route guard)
      const from = router.state.location.search?.from ?? "/dashboard";
      navigate({ to: from });
    },
  });
}
```

### Logout flow

```typescript
// hooks/useLogout.ts
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: () => apiClient.post("/api/auth/logout/"),

    onSettled: () => {
      // Clear ALL cached data — prevents stale user data leaking
      queryClient.clear();

      // Notify other tabs (see BroadcastChannel below)
      authBroadcast.postMessage("logout");

      navigate({ to: "/login" });
    },
  });
}
```

### Cross-tab logout with BroadcastChannel

```typescript
// lib/authBroadcast.ts
export const authBroadcast = new BroadcastChannel("auth");

// In AuthProvider or app root:
React.useEffect(() => {
  const handler = (event: MessageEvent) => {
    if (event.data === "logout") {
      queryClient.clear();
      navigate({ to: "/login" });
    }
  };

  authBroadcast.addEventListener("message", handler);
  return () => authBroadcast.removeEventListener("message", handler);
}, []);
```

---

## 4. JWT with silent refresh

If using JWT (simplejwt) with access + refresh tokens:

```typescript
// The recommended simplejwt cookie configuration in Django:
# settings.py
REST_FRAMEWORK = {
  "DEFAULT_AUTHENTICATION_CLASSES": [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
  ],
}

SIMPLE_JWT = {
  "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
  "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
  "AUTH_COOKIE": "access_token",
  "REFRESH_COOKIE": "refresh_token",
  "AUTH_COOKIE_HTTP_ONLY": True,
  "AUTH_COOKIE_SECURE": True,          # HTTPS only
  "AUTH_COOKIE_SAMESITE": "Strict",    # or "Lax"
}
```

### Axios interceptor for silent refresh

```typescript
// api/client.ts
import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,  // always send cookies
});

// Response interceptor: on 401, try to refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retried) {
      originalRequest._retried = true;

      try {
        // Attempt to get a new access token using the refresh cookie
        await axios.post("/api/auth/token/refresh/", {}, { withCredentials: true });
        // Retry the original request — the new access cookie is now set
        return apiClient(originalRequest);
      } catch {
        // Refresh failed — user is truly logged out
        queryClient.clear();
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);
```

The `axios-auth-refresh` library automates this pattern and handles concurrent request queuing during the refresh cycle.

---

## 5. Protected routes with TanStack Router

### Route context for auth

```typescript
// router.tsx
import { useAuth } from "@/contexts/AuthContext";

// Attach auth to router context so routes can access it
const rootRoute = createRootRouteWithContext<{ auth: ReturnType<typeof useAuth> }>()({
  component: RootLayout,
});

// In the RouterProvider:
function App() {
  const auth = useAuth();
  return (
    <RouterProvider
      router={router}
      context={{ auth }}   // injected into all route beforeLoad/loader contexts
    />
  );
}
```

### beforeLoad guard

```typescript
// routes/dashboard.tsx
export const Route = createFileRoute("/dashboard")({
  beforeLoad: ({ context, location }) => {
    if (!context.auth.isAuthenticated) {
      throw redirect({
        to: "/login",
        search: { from: location.href },  // save current location for post-login redirect
      });
    }
  },
  component: DashboardPage,
});
```

### Post-login redirect

```typescript
// routes/login.tsx
export const Route = createFileRoute("/login")({
  // Validate the search params type
  validateSearch: z.object({ from: z.string().optional() }),

  component: LoginPage,
});

function LoginPage() {
  const { from } = Route.useSearch();
  const login = useLogin();

  const handleLogin = async (credentials) => {
    await login.mutateAsync(credentials);
    navigate({ to: from ?? "/dashboard" });
  };
}
```

### Role-based access

```typescript
export const Route = createFileRoute("/admin")({
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) {
      throw redirect({ to: "/login" });
    }
    if (context.auth.user?.role !== "admin") {
      throw redirect({ to: "/dashboard" });  // or show 403 page
    }
  },
});
```

---

## 6. CSRF protection

Django's session auth and allauth both require a CSRF token on POST/PUT/PATCH/DELETE requests. The token is in the `csrftoken` cookie.

### Axios CSRF setup

```typescript
// api/client.ts
import Cookies from "js-cookie";

// Add X-CSRFToken header to all state-changing requests
apiClient.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase();

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method ?? "")) {
    const csrfToken = Cookies.get("csrftoken");
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken;
    }
  }

  return config;
});
```

### Django configuration for cookie-based CSRF

```python
# settings.py
CSRF_COOKIE_SAMESITE = "Strict"   # or "Lax" for cross-origin flows
CSRF_COOKIE_SECURE = True         # HTTPS only in production
CSRF_COOKIE_HTTPONLY = False      # must be False — JS needs to read it
CORS_ALLOW_CREDENTIALS = True     # django-cors-headers — allow cookies cross-origin
CORS_ALLOWED_ORIGINS = ["https://app.example.com"]
```

### django-allauth headless CSRF note

`django-allauth` headless mode sets its own session cookie architecture. The CSRF pattern still applies but ensure `SESSION_COOKIE_SAMESITE = "None"` and `SESSION_COOKIE_SECURE = True` if your frontend and Django are on different origins.

---

## 7. Global 401 handling

Rather than handling auth errors in each query, intercept at the Axios level:

```typescript
// api/client.ts (extend the interceptor above)
let isHandling401 = false;

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && !isHandling401) {
      isHandling401 = true;

      queryClient.clear();

      // Replace history so the login page doesn't get a "back" entry pointing at 401
      window.location.replace("/login");

      setTimeout(() => { isHandling401 = false; }, 1000);
    }

    return Promise.reject(error);
  }
);
```

The `isHandling401` flag prevents multiple simultaneous 401s from triggering multiple redirects (common when several queries fire at once on initial load).

---

## 8. OAuth flows (django-allauth headless)

### Redirect-based OAuth

```typescript
// Initiate OAuth — redirect to provider
function initiateGoogleOAuth() {
  // Django allauth headless provides this endpoint
  window.location.href = "/api/auth/google/login/?next=/dashboard";
}
```

### OAuth callback page

Django allauth handles the callback server-side. After completing OAuth, Django redirects to the frontend with the session cookie set. The callback page just needs to refetch `/api/me/` and redirect:

```typescript
// routes/auth/callback.tsx
export const Route = createFileRoute("/auth/callback")({
  component: OAuthCallback,
});

function OAuthCallback() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  React.useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["me"] }).then(() => {
      navigate({ to: "/dashboard" });
    });
  }, []);

  return <Spinner />;
}
```

---

## 9. Auth in MSW handlers (for tests)

```typescript
// test/handlers.ts
let isAuthenticated = false;

export const authHandlers = [
  http.get("/api/me/", () => {
    if (!isAuthenticated) {
      return HttpResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }
    return HttpResponse.json({ id: "1", email: "user@example.com", role: "user" });
  }),

  http.post("/api/auth/login/", async ({ request }) => {
    const { email, password } = await request.json() as any;
    if (email === "user@example.com" && password === "password") {
      isAuthenticated = true;
      return HttpResponse.json({ success: true });
    }
    return HttpResponse.json({ detail: "Invalid credentials" }, { status: 400 });
  }),

  http.post("/api/auth/logout/", () => {
    isAuthenticated = false;
    return HttpResponse.json({ success: true });
  }),
];

// Reset between tests:
afterEach(() => { isAuthenticated = false; });
```
