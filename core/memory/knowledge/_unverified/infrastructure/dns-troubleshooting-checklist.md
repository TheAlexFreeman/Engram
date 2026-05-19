---
created: '2026-04-22'
origin_session: memory/activity/2026/04/22/chat-001
source: external-research
trust: low
---

# DNS Troubleshooting Checklist — Subdomain → Render

Quick-reference checklist for diagnosing issues when a Bluehost-managed subdomain points to a Render-hosted service.

## Diagnostic Commands

```bash
# Check CNAME resolution
dig demo.example.com CNAME +short
# Expected: myapp.onrender.com.

# Check A record resolution (follows CNAME)
dig demo.example.com A +short
# Expected: Render's IP addresses

# Check for conflicting AAAA records
dig demo.example.com AAAA +short
# Expected: empty (no IPv6 records)

# Check CAA records on the parent domain
dig example.com CAA +short
# Expected: empty, or includes "letsencrypt.org"

# Check TLS certificate details
openssl s_client -connect demo.example.com:443 -servername demo.example.com < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates

# Global propagation check
# Visit https://dnschecker.org and enter demo.example.com
```

## Issue → Fix Quick Reference

| Symptom | Likely Cause | Fix |
|---|---|---|
| `dig` returns Bluehost IP, not Render | Stale A record on subdomain | Delete the A/AAAA record in Bluehost DNS zone; keep only the CNAME |
| `dig` returns NXDOMAIN | CNAME not added or not propagated | Add CNAME in Bluehost; wait up to 48h (usually less than 1h) |
| Render says "domain not verified" | DNS hasn't propagated to Render's resolvers | Wait 15 min, retry verification |
| Browser shows SSL warning / ERR_CERT_COMMON_NAME_INVALID | Render hasn't provisioned cert yet | Check Render dashboard for cert status; ensure no AAAA or Cloudflare proxy blocking |
| Browser shows "connection refused" on HTTPS | TLS cert not yet provisioned | Wait for Render to complete provisioning (check dashboard) |
| Django returns 400 | Domain not in ALLOWED_HOSTS | Add `'demo.example.com'` to ALLOWED_HOSTS |
| Django CSRF error on POST | Domain not in CSRF_TRUSTED_ORIGINS | Add `'https://demo.example.com'` (with scheme!) |
| Infinite redirect loop | SECURE_SSL_REDIRECT without SECURE_PROXY_SSL_HEADER | Add `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` |
| Cert renew fails months later | CAA record added after initial setup, missing letsencrypt.org | Add `0 issue "letsencrypt.org"` CAA record |