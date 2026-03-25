---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - react-performance.md
  - react-error-boundaries-suspense.md
  - vitest-rtl-msw.md
  - ../devops/sentry-fullstack-observability.md
  - react-hook-form-zod.md
  - tanstack-query.md
  - react-19-overview.md
  - ../devops/github-actions-cicd.md
---

# Vite Configuration for React

Vite is the build tool for this stack. It serves the dev server with HMR and builds to a static dist/ folder that can be served by Nginx or a CDN. This file covers the configuration patterns for development, testing, bundling, and production deployment.

---

## 1. Plugin choice: @vitejs/plugin-react vs. @vitejs/plugin-react-swc

| | `@vitejs/plugin-react` | `@vitejs/plugin-react-swc` |
|---|---|---|
| Transform | Babel | SWC (Rust) |
| Cold start | Moderate | Fast (SWC is ~20× faster) |
| HMR | React Fast Refresh | React Fast Refresh |
| Babel plugins | Full ecosystem | Limited SWC plugin support |
| Use when | Need custom Babel plugins (e.g., React Compiler, styled-components) | Pure React with no custom transforms |

```typescript
// Standard Babel plugin (more common):
import react from "@vitejs/plugin-react";

// SWC plugin (better for cold start with no custom transforms):
import react from "@vitejs/plugin-react-swc";
```

For the React Compiler (`babel-plugin-react-compiler`), you must use the Babel variant:

```typescript
react({
  babel: {
    plugins: ["babel-plugin-react-compiler"],
  },
}),
```

---

## 2. Environment variables

Vite has a strict separation between build-time variables (available everywhere) and client-exposed variables:

- **`VITE_`-prefixed variables** — embedded into the JavaScript bundle at build time; readable in the browser via `import.meta.env.VITE_*`
- **Non-prefixed variables** — only available in `vite.config.ts`, not exposed to the client

```bash
# .env (committed — public defaults)
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=MyApp

# .env.local (not committed — local overrides)
VITE_API_URL=http://localhost:8001

# .env.production (committed — production build values)
VITE_API_URL=https://api.myapp.com
```

```typescript
// In components / hooks:
const apiUrl = import.meta.env.VITE_API_URL;
const isDev = import.meta.env.DEV;       // boolean, true in dev
const isProd = import.meta.env.PROD;     // boolean, true in production build
const mode = import.meta.env.MODE;       // "development" | "production" | custom

// Build-time constant injection (for tree-shaking dead code by environment)
if (import.meta.env.DEV) {
  console.debug("Debug mode active");
}
```

### Accessing non-prefixed vars in config

```typescript
// vite.config.ts
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // loadEnv reads the .env* files for the current mode
  const env = loadEnv(mode, process.cwd(), "");  // "" prefix = all vars

  return {
    plugins: [...],
    define: {
      // Optionally expose a non-VITE_ var as a constant (not recommended unless necessary)
      __APP_VERSION__: JSON.stringify(env.npm_package_version),
    },
  };
});
```

### TypeScript types for env vars

```typescript
// src/env.d.ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_APP_NAME: string;
  // Add all your VITE_ vars here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

---

## 3. Dev server proxy

The most practical development setup: proxy `/api/` to Django so the browser always talks to localhost:5173, avoiding CORS entirely in development.

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
      // Optional: rewrite path if Django is mounted at a sub-path
      // rewrite: (path) => path.replace(/^\/api/, ""),
    },
    "/static": {
      target: "http://localhost:8000",
      changeOrigin: true,
    },
  },
},
```

With this setup:
- Fetch to `/api/users/` → Vite proxies to `http://localhost:8000/api/users/`
- Django sees the request as same-origin — no CORS headers needed in development
- `CORS_ALLOWED_ORIGINS` in Django is only needed for production

---

## 4. Path aliases

Absolute imports prevent deeply nested relative paths (`../../../components/Button`).

```typescript
// vite.config.ts
import path from "path";

resolve: {
  alias: {
    "@": path.resolve(__dirname, "./src"),
    "@components": path.resolve(__dirname, "./src/components"),
    "@api": path.resolve(__dirname, "./src/api"),
  },
},
```

**Must also configure TypeScript**:

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@api/*": ["./src/api/*"]
    }
  }
}
```

Vite's alias and TypeScript's `paths` are separate configurations and must be kept in sync.

---

## 5. Build optimization

### Basic production build

```bash
npm run build  # vite build → dist/
npm run preview  # vite preview → serves dist/ locally for verification
```

### manual chunks

By default, Vite splits chunks at async import boundaries. Override with `manualChunks` to guarantee what ends up in each chunk:

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        // Vendor chunk — stable, aggressively cached by browsers
        vendor: ["react", "react-dom"],

        // TanStack — changes on updates but separate from vendor
        tanstack: [
          "@tanstack/react-query",
          "@tanstack/react-router",
          "@tanstack/react-virtual",
        ],

        // Chakra — large; separate chunk helps with cache reuse
        chakra: ["@chakra-ui/react"],
      },
    },
  },
},
```

**Why chunk splitting matters for caching**: if React and your app code are in the same chunk, a single line of app code change invalidates the entire React bundle. Separating vendor makes `vendor.[hash].js` eternally cacheable.

### Other build options

```typescript
build: {
  target: "es2020",              // target modern browsers; avoids unnecessary transforms
  sourcemap: true,               // true for production debugging; "hidden" for Sentry without exposing to users
  assetsInlineLimit: 4096,       // files smaller than 4kb are base64-inlined; increase to reduce requests
  chunkSizeWarningLimit: 500,    // warn when chunks exceed 500kb (default)
  minify: "esbuild",             // esbuild (faster) or "terser" (smaller)
},
```

---

## 6. Bundle size analysis

```bash
npm run build  # visualizer plugin runs after build and opens report in browser
```

### Setup (see react-performance.md for details)

```typescript
// vite.config.ts
import { visualizer } from "rollup-plugin-visualizer";

plugins: [
  react(),
  // Only run visualizer during explicit analysis builds
  process.env.ANALYZE && visualizer({
    filename: "dist/bundle-report.html",
    open: true,
    gzipSize: true,
    brotliSize: true,
  }),
].filter(Boolean),
```

```bash
ANALYZE=true npm run build
```

### size-limit in CI

```bash
npm install --save-dev @size-limit/preset-app size-limit
```

```json
// package.json
{
  "size-limit": [
    {
      "path": "dist/assets/index-*.js",
      "limit": "200 KB"
    },
    {
      "path": "dist/assets/vendor-*.js",
      "limit": "150 KB"
    }
  ]
}
```

```yaml
# .github/workflows/ci.yml
- name: Build and check bundle size
  run: |
    npm run build
    npx size-limit
```

---

## 7. Vitest config sharing

Vitest reads `vite.config.ts` automatically — you get the same plugins, aliases, and transforms in tests as in the build. The `test` config block is the only addition needed:

```typescript
// vite.config.ts — single file for both build and test config
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },

  // Test config — ignored by `vite build`
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
```

If you need a separate test config (e.g., different plugins), use `vitest.config.ts` which merges with `vite.config.ts`:

```typescript
// vitest.config.ts
import { mergeConfig } from "vite";
import { defineConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
    },
  })
);
```

---

## 8. Docker multi-stage build

Two-stage Docker build: Node.js compiles the app, Nginx serves the static output.

```dockerfile
# Dockerfile

# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app

# Copy package files first for layer caching
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

COPY . .

# Build args become VITE_ env vars at build time
ARG VITE_API_URL
ARG VITE_APP_NAME
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine AS runner

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom Nginx config for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### nginx.conf for SPA routing

The critical piece: `try_files` falls back to `index.html` so that client-side routes (like `/dashboard/settings`) are handled by React Router, not Nginx 404:

```nginx
# nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Compression
    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    # Long-term caching for fingerprinted assets (filename contains hash)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback — all routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Docker build with build args

```bash
docker build \
  --build-arg VITE_API_URL=https://api.myapp.com \
  --build-arg VITE_APP_NAME=MyApp \
  -t myapp-frontend:latest \
  .
```

**Important**: `VITE_` vars are embedded at build time, not runtime. If the API URL needs to change at runtime (e.g., same image, multiple environments), pass it via a runtime config file served at `/config.json` and fetched at app startup — but this adds complexity and is usually not worth it.

---

## 9. PWA (optional, with vite-plugin-pwa)

```bash
npm install -D vite-plugin-pwa
```

```typescript
// vite.config.ts
import { VitePWA } from "vite-plugin-pwa";

plugins: [
  react(),
  VitePWA({
    registerType: "autoUpdate",
    workbox: {
      globPatterns: ["**/*.{js,css,html,ico,png,svg}"],
      runtimeCaching: [
        {
          urlPattern: /^\/api\//,
          handler: "NetworkFirst",
          options: {
            cacheName: "api-cache",
            expiration: { maxEntries: 100, maxAgeSeconds: 300 },
          },
        },
      ],
    },
    manifest: {
      name: "My App",
      short_name: "App",
      theme_color: "#ffffff",
      icons: [...],
    },
  }),
],
```

PWA adds a service worker that caches assets for offline use. The `NetworkFirst` strategy for `/api/` means: try the network first, fall back to cache if offline. Do not add PWA until the app's caching strategy is intentionally designed — a misconfigured service worker can serve stale responses in ways that are hard to debug.
