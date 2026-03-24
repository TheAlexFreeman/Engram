---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [dns, tls, tcp, networking, https, cdn, certificates]
related:
  - http-protocol-reference.md
  - ../devops/nginx-django-react.md
  - ../devops/docker-production-config.md
  - ../devops/zero-downtime-deploys.md
---

# DNS, TLS, and Networking

Practical reference for the network layers underneath HTTP. Covers DNS resolution, TCP connections, TLS handshakes, HTTPS certificate management, CDNs, and debugging tools. Framework-agnostic foundations relevant to any Django+React production deployment.

## 1. DNS Resolution Chain

When a browser navigates to `api.example.com`:

```
Browser cache  →  OS resolver cache  →  Recursive resolver (ISP/Cloudflare/Google)
                                            │
                                            ├─ Root nameserver (.)
                                            ├─ TLD nameserver (.com)
                                            └─ Authoritative nameserver (example.com)
                                                  │
                                                  └─ Returns: A 93.184.216.34
```

Each layer caches the answer for the duration of the **TTL** (Time To Live) set by the authoritative server. A TTL of 300 means "cache this for 5 minutes."

### DNS Record Types That Matter

| Type | Purpose | Example |
|------|---------|---------|
| **A** | Maps hostname → IPv4 address | `api.example.com → 93.184.216.34` |
| **AAAA** | Maps hostname → IPv6 address | `api.example.com → 2606:2800:220:1:...` |
| **CNAME** | Alias to another hostname | `www.example.com → example.com` |
| **MX** | Mail server for the domain | `example.com → mail.example.com (priority 10)` |
| **TXT** | Arbitrary text (SPF, DKIM, verification) | `"v=spf1 include:_spf.google.com ~all"` |
| **NS** | Authoritative nameservers for a zone | `example.com → ns1.provider.com` |
| **SRV** | Service endpoints with port and priority | `_sip._tcp.example.com → 5060 sip.example.com` |

### TTL Strategy

| Scenario | TTL | Rationale |
|----------|-----|-----------|
| Stable production | 3600 (1 hr) | Reduce DNS lookup overhead |
| Before migration/failover | 60–300 | Fast propagation of IP changes |
| CDN-fronted (Cloudflare, etc.) | CDN-managed | CDN handles its own edge TTLs |
| Development | 60 | Quick iteration on record changes |

**Before changing DNS for a migration**: Lower TTL 24–48 hours in advance so stale caches expire before the cutover. After migration, raise TTL back to normal.

## 2. TCP Connection Lifecycle

Every HTTP/1.1 or HTTP/2-over-TLS connection runs over TCP:

```
Client              Server
  │── SYN ──────────→│         1. Client initiates
  │←── SYN-ACK ─────│         2. Server acknowledges
  │── ACK ──────────→│         3. Connection established (3-way handshake)
  │                   │
  │←→ Data exchange ←→│        4. HTTP request/response pairs
  │                   │
  │── FIN ──────────→│         5. Client initiates close
  │←── FIN-ACK ─────│         6. Server confirms
```

### Key Concepts

**Congestion window (CWND)**: TCP starts slow and ramps up throughput. New connections send a few packets (initial CWND ≈ 10 segments ≈ 14 KB), then grow as ACKs arrive. This is **slow start** — first-byte latency is always higher than steady-state.

**Keep-alive**: HTTP/1.1 defaults to `Connection: keep-alive`, reusing the TCP connection for multiple requests. Nginx config `keepalive_timeout 65;` controls how long idle connections survive.

**Impact on web apps**: The 3-way handshake adds 1 RTT before any data flows. With TLS, add another 1–2 RTTs. This is why connection reuse (keep-alive, HTTP/2 multiplexing) and CDN edge servers (shorter RTT) matter for performance.

## 3. TLS 1.3 Handshake

TLS encrypts the connection after TCP handshake:

```
Client                                  Server
  │── ClientHello (supported ciphers) ──→│     1 RTT
  │←── ServerHello + Certificate + Finished ──│
  │── Finished ──────────────────────────→│
  │                                        │
  │←═══════ Encrypted data ═══════════════→│
```

**TLS 1.3 improvements over 1.2**:
- **1-RTT handshake** (1.2 was 2 RTTs) — reduces connection setup time
- **0-RTT resumption** — returning clients skip the handshake entirely (with replay risk caveats)
- **Removed weak ciphers** — only AEAD cipher suites (AES-GCM, ChaCha20-Poly1305)
- **Forward secrecy by default** — all key exchanges use ephemeral keys

### Certificate Chain

```
Root CA (trusted by OS/browser)
  └── Intermediate CA (signed by root)
        └── Leaf certificate (your domain, signed by intermediate)
```

The server sends the leaf + intermediate(s). The browser validates up to a trusted root. Missing intermediates = TLS errors for some clients.

### Cipher Suites (TLS 1.3)

| Suite | Notes |
|-------|-------|
| `TLS_AES_256_GCM_SHA384` | General-purpose, hardware-accelerated on most CPUs |
| `TLS_AES_128_GCM_SHA256` | Slightly faster, widely supported |
| `TLS_CHACHA20_POLY1305_SHA256` | Better on devices without AES hardware (mobile) |

Nginx config:
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;   # let client choose (TLS 1.3 best practice)
```

## 4. HTTPS in Practice

### Certificate Management with Let's Encrypt

Let's Encrypt provides free DV (Domain Validation) certificates via the ACME protocol:

```bash
# Certbot — most common ACME client
certbot certonly --nginx -d api.example.com -d www.example.com

# Auto-renewal (cron or systemd timer)
certbot renew --quiet
# Certificates renew 30 days before expiry (90-day lifetime)
```

**Docker deployment**: Use a reverse proxy like Traefik or `nginx-proxy` + `acme-companion` for automatic certificate management in Docker Compose environments.

### HSTS (HTTP Strict Transport Security)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

HSTS tells browsers: "Always use HTTPS for this domain, even if the user types `http://`." Once set, the browser won't even attempt an HTTP connection. The `preload` directive submits the domain to browser preload lists for protection on first visit.

**Caution**: Setting a long `max-age` before HTTPS is fully working locks users out. Start with `max-age=300` and increase after confirming everything works.

## 5. CDN Fundamentals

A CDN (Content Delivery Network) places edge servers near users, caching content closer to the browser:

```
Browser → CDN Edge (nearby) → Origin Server (your infra)
           ↓ cache hit
        Serve directly (low latency)
```

### Key Concepts

| Concept | Meaning |
|---------|---------|
| **Edge server** | CDN node geographically close to the user |
| **Origin** | Your actual server (Nginx → Django/React) |
| **Origin shield** | Intermediate CDN layer that collapses cache misses to a single origin request |
| **Cache key** | URL + headers that determine cache uniqueness (e.g., URL + `Accept-Encoding`) |
| **Purge/Invalidation** | Delete cached content before TTL expiry |

### CDN Caching Strategy

| Resource | CDN Caching | Rationale |
|----------|-------------|-----------|
| Vite-built JS/CSS (hashed filenames) | Long TTL (1 year), `immutable` | Hash changes on every build |
| `index.html` | Short TTL or `no-cache` | Must pick up new bundle references on deploy |
| API responses | Generally no CDN caching | User-specific data, auth-dependent |
| Public API (catalog, etc.) | Short TTL (60s), `s-maxage` | Shared, changes infrequently |
| Static media (images, fonts) | Medium TTL (1 day) | Stable content |

### DNS-Based Routing

CDNs use DNS to route users to the nearest edge:
1. User resolves `cdn.example.com` via DNS
2. CDN's authoritative DNS returns the IP of the closest edge server
3. Edge serves cached content or fetches from origin on miss

This is why CDN-fronted domains often have very low TTLs (60s) — they need DNS flexibility to reroute traffic during outages.

## 6. Connection Optimization

### Resource Hints

HTML hints that help the browser prepare connections early:

```html
<!-- Resolve DNS early for API domain -->
<link rel="dns-prefetch" href="https://api.example.com">

<!-- Full connection setup (DNS + TCP + TLS) -->
<link rel="preconnect" href="https://api.example.com">

<!-- Prefetch a resource for the next navigation -->
<link rel="prefetch" href="/next-page-data.json">
```

`preconnect` eliminates 1–3 RTTs of connection setup before the first API call. Use for your API origin, font CDNs, and analytics endpoints. Don't preconnect to too many origins — each connection costs memory and CPU.

### HTTP/2 Impact on Connection Strategy

HTTP/1.1: browsers open 6 parallel TCP connections per domain → domain sharding was common.
HTTP/2: one TCP connection with multiplexed streams → domain sharding is harmful (prevents multiplexing).

**Modern recommendation**: Serve everything from one origin (or one CDN domain) to maximize HTTP/2 multiplexing. Separate domains only when needed for cookie scoping or security boundaries.

## 7. Practical Debugging

### `dig` — DNS Queries

```bash
dig api.example.com           # default A record query
dig api.example.com AAAA      # IPv6
dig api.example.com +short    # just the IP
dig @8.8.8.8 api.example.com  # query specific resolver (Google DNS)
dig api.example.com +trace    # follow the full resolution chain
```

### `curl -v` — Full HTTP Exchange

```bash
# Show connection details, TLS handshake, headers, body
curl -v https://api.example.com/health/

# Timing breakdown
curl -w "\nDNS: %{time_namelookup}s\nTCP: %{time_connect}s\nTLS: %{time_appconnect}s\nFirst byte: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s https://api.example.com/

# Send with specific headers
curl -H "Accept: application/json" -H "Authorization: Bearer TOKEN" \
  https://api.example.com/api/orders/
```

### `openssl s_client` — TLS Inspection

```bash
# View certificate chain and TLS negotiation
openssl s_client -connect api.example.com:443 -servername api.example.com

# Check certificate expiry
echo | openssl s_client -connect api.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates
```

### Browser DevTools (Network Tab)

- **Waterfall**: Shows DNS, TCP, TLS, request, response timing per resource
- **Protocol column**: Confirms h2 or h3 is active
- **Size**: Transferred vs actual (compression ratio)
- **Disable cache**: Checkbox to bypass browser cache during debugging
- **Throttling**: Simulate slow connections (3G, slow 4G)

## Sources

- MDN DNS: https://developer.mozilla.org/en-US/docs/Glossary/DNS
- Cloudflare Learning — DNS: https://www.cloudflare.com/learning/dns/what-is-dns/
- RFC 8446 (TLS 1.3): https://www.rfc-editor.org/rfc/rfc8446
- Let's Encrypt docs: https://letsencrypt.org/docs/
- MDN Resource Hints: https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/rel/preconnect
