---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [owasp, xss, csrf, security, csp, injection, frontend]
related:
  - web-storage-and-state.md
  - cors-in-depth.md
  - http-protocol-reference.md
  - ../django/django-security.md
  - ../react/react-auth-patterns.md
  - ../react/react-error-boundaries-suspense.md
---

# OWASP Frontend Security

The OWASP Top 10 from a frontend developer's perspective. Covers the attack vectors that originate in or are mitigated by the browser layer of a Django + React stack. This file focuses on the *frontend* attack surface; see [django-security.md](../django/django-security.md) for server-side depth (auth, password hashing, rate limiting, secrets).

## 1. Cross-Site Scripting (XSS)

XSS is the #1 frontend vulnerability. An attacker injects JavaScript that executes in a victim's browser, with full access to the page's DOM, cookies (non-httpOnly), localStorage, and authenticated API calls.

### XSS Types

| Type | Injection Point | Persistence | Example |
|------|----------------|-------------|---------|
| **Stored** | Database → server → page | Permanent until removed | Malicious comment HTML rendered by server |
| **Reflected** | URL parameter → server → page | Per-request | Search query echoed in results page |
| **DOM-based** | Client-side JS reads from URL/storage | Per-request | `innerHTML = location.hash.slice(1)` |

### React's XSS Protection

React escapes all values rendered in JSX by default:

```jsx
// SAFE — React escapes the string, renders as text
const userInput = '<script>alert("xss")</script>';
return <p>{userInput}</p>;
// Renders: <p>&lt;script&gt;alert("xss")&lt;/script&gt;</p>
```

**The escape hatch**: `dangerouslySetInnerHTML` bypasses React's escaping. If you must use it, sanitize with a library first:

```jsx
import DOMPurify from 'dompurify';

// Sanitize before rendering
const clean = DOMPurify.sanitize(untrustedHtml);
return <div dangerouslySetInnerHTML={{ __html: clean }} />;
```

### DOM XSS Sinks to Avoid

| Dangerous | Safe Alternative |
|-----------|------------------|
| `element.innerHTML = userInput` | `element.textContent = userInput` |
| `document.write(userInput)` | Don't use `document.write` |
| `eval(userInput)` | Never eval untrusted input |
| `new Function(userInput)` | Parse JSON with `JSON.parse` |
| `setTimeout(userInputString, ...)` | `setTimeout(functionRef, ...)` |
| `location.href = userInput` | Validate URL scheme (`https://` only) |
| `<a href={userInput}>` | Validate: no `javascript:` URLs |

### URL Scheme Validation

```javascript
// React — prevent javascript: URLs in user-provided links
function SafeLink({ href, children }) {
  const isValid = /^https?:\/\//i.test(href);
  return isValid ? <a href={href}>{children}</a> : <span>{children}</span>;
}
```

React warns about `javascript:` URLs in JSX but doesn't block them in all cases. Always validate user-provided URLs.

## 2. Content Security Policy (CSP)

CSP is a response header that tells the browser which sources of content are allowed. It's the strongest XSS mitigation layer:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-abc123';
  style-src 'self' 'unsafe-inline';
  img-src 'self' https://cdn.example.com;
  connect-src 'self' https://api.example.com https://*.sentry.io;
  font-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

### Key Directives

| Directive | Controls | Notes |
|-----------|----------|-------|
| `default-src` | Fallback for all fetch directives | Start restrictive: `'self'` |
| `script-src` | JavaScript sources | Use nonces, avoid `'unsafe-inline'` and `'unsafe-eval'` |
| `style-src` | CSS sources | Chakra/emotion may need `'unsafe-inline'` or nonces |
| `connect-src` | `fetch`, XHR, WebSocket targets | Must include API and Sentry origins |
| `img-src` | Image sources | Include CDN, data URIs if needed |
| `frame-ancestors` | Who can embed your page in iframe | `'none'` = no framing (replaces `X-Frame-Options`) |
| `base-uri` | Restricts `<base>` tag | `'self'` prevents base tag injection |
| `form-action` | Where forms can submit | `'self'` prevents form action hijacking |

### Nonce-Based Script Policy

```html
<!-- Server generates a unique nonce per request -->
<script nonce="abc123">
  // Inline script allowed because nonce matches CSP header
</script>
```

Django 6.0's built-in CSP support generates nonces automatically. Vite's built SPA files are external scripts (allowed by `script-src 'self'`), so nonces mainly matter for inline scripts.

### Report-Only Mode

```
Content-Security-Policy-Report-Only: default-src 'self'; report-uri /csp-report/
```

Deploy in report-only first to discover what would break. Review violation reports, then switch to enforcement.

### Chakra UI / CSS-in-JS and CSP

CSS-in-JS libraries (Emotion, Chakra) inject `<style>` tags at runtime and need either:
- `'unsafe-inline'` in `style-src` (weakens CSP for styles)
- A nonce passed to the style injection engine

Chakra v3 with static extraction (Panda CSS mode) avoids runtime style injection, making strict CSP easier.

## 3. Cross-Site Request Forgery (CSRF)

CSRF tricks a victim's browser into making an authenticated request to your API from an attacker's site. The browser automatically includes cookies (session, auth).

```html
<!-- Attacker's page — auto-submits form to your API -->
<form action="https://api.yoursite.com/api/transfer/" method="POST">
  <input type="hidden" name="to" value="attacker">
  <input type="hidden" name="amount" value="10000">
</form>
<script>document.forms[0].submit();</script>
```

### Defenses

| Defense | How It Works | Stack Component |
|---------|-------------|-----------------|
| **CSRF token** (synchronizer pattern) | Random token in cookie + form/header; server validates match | Django middleware |
| **SameSite cookies** | `Lax` prevents cookie from being sent on cross-site POST | Browser + Django config |
| **Custom headers** | `X-CSRFToken` header can't be set by HTML forms or simple requests | React `fetch` config |
| **CORS** | Prevents cross-origin JavaScript from reading responses | Django cors-headers |

**Django + React pattern**:
```javascript
// React reads the CSRF token from the cookie
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

// Include in every state-changing request
fetch('/api/orders/', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'X-CSRFToken': getCsrfToken(),
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(data),
});
```

See [cors-in-depth.md](cors-in-depth.md) for how CORS and CSRF interact and why both are needed.

## 4. Sensitive Data Exposure

### What Not to Store in the Browser

| Data | Storage | Risk |
|------|---------|------|
| Passwords | ❌ Never | XSS → full account compromise |
| API secrets/keys | ❌ Never in frontend code | Source inspection, XSS |
| PII (SSN, financial) | ❌ Avoid, or encrypt | XSS → data theft |
| Auth tokens | Memory variable or httpOnly cookie | localStorage → XSS-readable |
| Non-sensitive preferences | localStorage is fine | Low-value data |

### Source Code Exposure

Everything in the frontend bundle is public. Vite minification and hashing obscure but don't protect code.

- **Never embed secrets** in frontend code (API keys, database URLs)
- Use server-side environment variables for secrets
- Public API keys (Stripe publishable, Sentry DSN) are fine — they're designed to be public
- `.env` files: Vite exposes variables prefixed with `VITE_` — only put non-secret config there

## 5. Injection via Third-Party Scripts

### Supply Chain Risk

Every `<script src="...">` from a third party runs with full access to your page:

| Mitigation | Implementation |
|------------|----------------|
| **Subresource Integrity (SRI)** | `<script src="cdn/lib.js" integrity="sha384-abc..." crossorigin>` |
| **CSP** | Whitelist specific CDN origins in `script-src` |
| **Lock dependency versions** | `package-lock.json` / `pnpm-lock.yaml` |
| **Audit dependencies** | `npm audit`, `pnpm audit`, Dependabot/Renovate |
| **Minimal third-party scripts** | Self-host what you can; avoid marketing tag soup |

### SRI (Subresource Integrity)

```html
<script src="https://cdn.example.com/lib@3.2.1/lib.min.js"
        integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"
        crossorigin="anonymous"></script>
```

If the CDN-served file is tampered with, the browser refuses to execute it. Vite-built assets are self-hosted so SRI mainly protects external CDN scripts.

## 6. Clickjacking

An attacker embeds your site in an invisible iframe and tricks users into clicking hidden buttons:

```html
<!-- Attacker's page -->
<iframe src="https://yoursite.com/settings/delete-account"
        style="opacity: 0; position: absolute; top: 0;"></iframe>
<button style="position: absolute; top: 0;">Click for prize!</button>
```

### Defenses

```
# CSP frame-ancestors (modern, recommended)
Content-Security-Policy: frame-ancestors 'none';

# X-Frame-Options (legacy fallback)
X-Frame-Options: DENY
```

Django sets `X-Frame-Options: DENY` by default via `XFrameOptionsMiddleware`.

## 7. Open Redirect

If your app redirects based on a URL parameter, attackers can craft links that redirect to phishing sites:

```
https://yoursite.com/login?next=https://evil.com/fake-login
```

### Defenses

```javascript
// Validate redirect URLs — only allow relative paths or same-origin
function safeRedirect(url, fallback = '/') {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin ? parsed.pathname : fallback;
  } catch {
    return fallback;
  }
}
```

Django's `login` view validates `next` against `ALLOWED_REDIRECT_HOSTS`. Implement similar validation for any client-side redirects.

## 8. Security Headers Checklist

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | (see section 2) | XSS mitigation |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS enforcement |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | Clickjacking protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable unused browser features |

Django's `SecurityMiddleware` sets most of these. Nginx can add headers that Django doesn't (`Permissions-Policy`).

## 9. React-Specific Security Patterns

```jsx
// 1. Escape user content (React does this by default in JSX)
<p>{user.name}</p>  // Safe: escaped

// 2. Validate URLs before rendering as links
<a href={isValidUrl(url) ? url : '#'}>Link</a>

// 3. Sanitize HTML if dangerouslySetInnerHTML is unavoidable
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />

// 4. Use httpOnly cookies for auth (not accessible to XSS)
// 5. CSP nonces for any inline scripts

// 6. Avoid exposing stack traces in production
// React error boundaries catch rendering errors — show friendly UI
// Sentry captures the real error server-side
```

## Sources

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP XSS Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Scripting_Prevention_Cheat_Sheet.html
- MDN Content Security Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- MDN SameSite cookies: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite
- DOMPurify: https://github.com/cure53/DOMPurify
