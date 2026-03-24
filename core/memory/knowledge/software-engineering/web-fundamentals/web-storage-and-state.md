---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [web-storage, localstorage, sessionstorage, indexeddb, cookies, cache-api]
related:
  - javascript-core-patterns.md
  - owasp-frontend-security.md
  - http-protocol-reference.md
  - ../react/react-auth-patterns.md
  - ../react/tanstack-query.md
---

# Web Storage and Client-Side State

The browser provides several persistence mechanisms with different capacity, lifetime, and security characteristics. Choosing the right one depends on what you're storing, how long it should survive, and who should be able to read it.

## 1. Storage Comparison

| Storage | Capacity | Lifetime | Accessible From | Sent to Server? | Async? |
|---------|----------|----------|-----------------|-----------------|--------|
| **Cookies** | ~4 KB per cookie | Until expiry or session | Same-origin (configurable with Domain/Path) | **Yes** — every request | No |
| **localStorage** | ~5-10 MB | Until explicitly cleared | Same origin | No | No |
| **sessionStorage** | ~5-10 MB | Until tab closes | Same origin, **same tab only** | No | No |
| **IndexedDB** | 100s of MB+ | Until explicitly cleared | Same origin | No | **Yes** |
| **Cache API** | 100s of MB+ | Until explicitly cleared | Same origin | No | **Yes** |

**"Same origin"** = same scheme + host + port. `http://example.com` and `https://example.com` are different origins with separate storage.

## 2. Cookies

```javascript
// Set a cookie (client-side — visible to JS unless httpOnly)
document.cookie = "theme=dark; Path=/; Max-Age=31536000; SameSite=Lax; Secure";

// Read all cookies (returns one concatenated string)
const cookies = document.cookie; // "theme=dark; session_id=abc123"

// Delete a cookie (set Max-Age=0 or Expires in the past)
document.cookie = "theme=; Path=/; Max-Age=0";
```

### Cookie Attributes

| Attribute | Purpose | Default |
|-----------|---------|---------|
| `Path=/` | Cookie sent for all paths under this prefix | Current directory |
| `Domain=.example.com` | Sent to subdomains too | Exact hostname only |
| `Max-Age=N` | Expires in N seconds | Session (until browser closes) |
| `Expires=date` | Absolute expiry (older format) | Session |
| `Secure` | Only sent over HTTPS | Not set |
| `HttpOnly` | **Not accessible via JavaScript** | Not set |
| `SameSite=Strict\|Lax\|None` | CSRF protection | `Lax` (modern browsers) |

### SameSite Values

| Value | Behavior | Use Case |
|-------|----------|----------|
| `Strict` | Cookie never sent on cross-site requests (not even link clicks) | High-security cookies |
| `Lax` | Sent on top-level navigations (link clicks) but not embedded requests (fetch, iframe) | Default, good balance |
| `None` | Sent on all cross-site requests (**requires `Secure`**) | Cross-domain APIs, SSO |

**Django session cookie**: Django sets `SESSION_COOKIE_SAMESITE = 'Lax'` and `SESSION_COOKIE_HTTPONLY = True` by default. The CSRF cookie is `HttpOnly=False` by default so JavaScript can read it for `X-CSRFToken` headers.

See [react-auth-patterns.md](../react/react-auth-patterns.md) for token vs session storage trade-offs in a Django+React stack.

## 3. localStorage and sessionStorage

Both share the Web Storage API:

```javascript
// Store (strings only — must JSON.stringify objects)
localStorage.setItem('user', JSON.stringify({ id: 1, name: 'Alex' }));

// Retrieve
const user = JSON.parse(localStorage.getItem('user'));  // null if not set

// Remove
localStorage.removeItem('user');

// Clear all
localStorage.clear();

// Check available space (approximate)
const used = new Blob(Object.values(localStorage)).size;
```

### localStorage vs sessionStorage

| Feature | localStorage | sessionStorage |
|---------|-------------|----------------|
| Survives page reload | Yes | Yes |
| Survives tab close | Yes | **No** |
| Shared across tabs | **Yes** (same origin) | **No** (per tab) |
| `storage` event fires | **Yes** (in other tabs) | No |

### Cross-Tab Communication via `storage` Event

```javascript
// Tab A writes
localStorage.setItem('notification', JSON.stringify({ type: 'logout', at: Date.now() }));

// Tab B listens
window.addEventListener('storage', (e) => {
  if (e.key === 'notification') {
    const data = JSON.parse(e.newValue);
    if (data.type === 'logout') redirectToLogin();
  }
});
```

The `storage` event fires in **other** tabs (not the one that wrote). Useful for syncing logout, theme changes, or auth state across tabs.

### Common Patterns

```javascript
// Cache with expiry
function setWithExpiry(key, value, ttlMs) {
  const item = { value, expiry: Date.now() + ttlMs };
  localStorage.setItem(key, JSON.stringify(item));
}

function getWithExpiry(key) {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  const item = JSON.parse(raw);
  if (Date.now() > item.expiry) {
    localStorage.removeItem(key);
    return null;
  }
  return item.value;
}

// TanStack Query persistence (optional)
// tanstack-query can persist its cache to localStorage for instant
// page loads, then revalidate in the background (stale-while-revalidate)
```

### Gotchas

- **Strings only**: Forgetting `JSON.stringify`/`JSON.parse` stores `[object Object]`.
- **Synchronous**: Blocks the main thread. Fine for small reads, bad for large datasets.
- **Quota exceeded**: Catch `QuotaExceededError` when writing.
- **Private/incognito**: Some browsers limit storage or clear it on session end.
- **No atomic operations**: Concurrent writes from multiple tabs can race. Use `storage` events for coordination.

## 4. IndexedDB

Asynchronous, transactional object store for large structured data:

```javascript
// Open database (version bump triggers upgrade)
const request = indexedDB.open('myApp', 1);

request.onupgradeneeded = (event) => {
  const db = event.target.result;
  // Create object store (like a table)
  const store = db.createObjectStore('orders', { keyPath: 'id' });
  store.createIndex('status', 'status', { unique: false });
};

request.onsuccess = (event) => {
  const db = event.target.result;

  // Write
  const tx = db.transaction('orders', 'readwrite');
  tx.objectStore('orders').put({ id: 42, status: 'shipped', items: [...] });

  // Read
  const readTx = db.transaction('orders', 'readonly');
  const getReq = readTx.objectStore('orders').get(42);
  getReq.onsuccess = () => console.log(getReq.result);

  // Query by index
  const idx = readTx.objectStore('orders').index('status');
  const cursorReq = idx.openCursor(IDBKeyRange.only('pending'));
  cursorReq.onsuccess = (e) => {
    const cursor = e.target.result;
    if (cursor) {
      console.log(cursor.value);
      cursor.continue();
    }
  };
};
```

**When to use IndexedDB**:
- Offline-capable apps (cache API responses for offline use)
- Large datasets that exceed `localStorage` limits
- Structured data with indexes (query by field)
- Binary blobs (images, files)

**Wrappers**: The raw IndexedDB API is callback-heavy. Use `idb` (by Jake Archibald) for a Promise-based wrapper:

```javascript
import { openDB } from 'idb';

const db = await openDB('myApp', 1, {
  upgrade(db) {
    db.createObjectStore('orders', { keyPath: 'id' });
  },
});

await db.put('orders', { id: 42, status: 'shipped' });
const order = await db.get('orders', 42);
```

## 5. Cache API (Service Worker Cache)

The Cache API stores HTTP request/response pairs, primarily used by Service Workers for offline support:

```javascript
// In a Service Worker
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      // Return cached response or fetch from network
      return cached || fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open('v1').then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

// Programmatic cache management (works in main thread too)
const cache = await caches.open('api-v1');
await cache.put('/api/products/', new Response(JSON.stringify(data)));
const response = await cache.match('/api/products/');
```

### Caching Strategies

| Strategy | Behavior | Use For |
|----------|----------|---------|
| **Cache First** | Check cache, fall back to network | Static assets, fonts |
| **Network First** | Try network, fall back to cache | API data, content pages |
| **Stale While Revalidate** | Return cache immediately, update from network in background | Good balance of speed and freshness |
| **Cache Only** | Only serve from cache | Pre-cached app shell |
| **Network Only** | Always go to network | Auth endpoints, analytics |

## 6. Storage Eviction and Quotas

Browsers can evict storage under pressure (low disk space). The eviction priority:

1. **First to go**: Cache API, IndexedDB (in LRU order by origin)
2. **Protected**: localStorage, sessionStorage, cookies (smaller quotas = less pressure)
3. **Persistent storage**: Origins that request `navigator.storage.persist()` are protected from eviction

```javascript
// Request persistent storage (browser may prompt user)
const persistent = await navigator.storage.persist();
console.log(persistent ? 'Storage is persistent' : 'Storage may be evicted');

// Check storage estimate
const estimate = await navigator.storage.estimate();
console.log(`Used: ${estimate.usage} / ${estimate.quota} bytes`);
```

## 7. Choosing the Right Storage

| Scenario | Storage | Why |
|----------|---------|-----|
| Auth tokens (session-based) | **httpOnly cookie** | Not accessible to XSS |
| Auth tokens (SPA token-based) | **memory (variable)** | Cleared on page close, not in storage |
| User preferences (theme, language) | **localStorage** | Persists, small, synchronous |
| Form draft (unsaved work) | **sessionStorage** | Per-tab, dies with tab |
| Offline data cache | **IndexedDB** | Large, structured, async |
| Pre-cached assets for PWA | **Cache API** | HTTP request/response pairs |
| CSRF token | **cookie** (non-httpOnly) | JS needs to read it for headers |

**Security rule**: Never store sensitive data (passwords, PII, unencrypted tokens) in `localStorage` or `sessionStorage` — XSS can read them. Use `httpOnly` cookies or in-memory variables.

See [owasp-frontend-security.md](owasp-frontend-security.md) for the XSS threat model and why storage choice matters for security.

## Sources

- MDN Web Storage API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API
- MDN IndexedDB: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
- MDN Cache API: https://developer.mozilla.org/en-US/docs/Web/API/Cache
- MDN Storage API (quotas): https://developer.mozilla.org/en-US/docs/Web/API/Storage_API
- Jake Archibald — idb library: https://github.com/jakearchibald/idb
