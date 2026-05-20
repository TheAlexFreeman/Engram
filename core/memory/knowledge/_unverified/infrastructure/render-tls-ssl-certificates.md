---
created: '2026-04-22'
origin_session: memory/activity/2026/04/22/chat-001
source: external-research
trust: low
---

# Render TLS/SSL Certificates for Custom Domains

## How It Works

Render automatically provisions free TLS certificates via **Let's Encrypt** and **Google Trust Services** for every custom domain. Certificates are renewed automatically before expiration. No manual setup is needed once DNS is correctly configured.

## Provisioning Flow

1. You add a custom domain in Render and configure the DNS record.
2. Render detects the DNS record and begins domain verification.
3. Once verified, Render requests a TLS certificate from Let's Encrypt.
4. Let's Encrypt validates domain ownership via HTTP-01 challenge (Render handles this automatically).
5. Certificate is installed — HTTPS works on your custom domain.

Typical time from DNS propagation to working HTTPS: **5–30 minutes**.

## Troubleshooting Certificate Issues

### Certificate stuck in "Pending" or not provisioning

1. **DNS not pointing to Render.** Double-check that your CNAME (or ANAME/ALIAS) is correct and has propagated. Use `dig demo.example.com CNAME` or an online tool like https://dnschecker.org.
2. **Conflicting AAAA records.** IPv6 records on the subdomain can prevent Render from receiving the HTTP-01 challenge. Remove them.
3. **CAA records blocking issuance.** If your domain has a CAA record, it must include `letsencrypt.org` (and/or `pki.goog` for Google Trust Services). Check with `dig example.com CAA`. If there's no CAA record at all, that's fine — it means all CAs are allowed.
4. **Cloudflare proxy intercepting.** If using Cloudflare, the orange-cloud proxy terminates TLS before traffic reaches Render, preventing the HTTP-01 challenge. Set the record to **DNS only** (grey cloud) until the certificate is provisioned.
5. **Recent domain transfer.** Some registrars lock DNS for 24–72 hours after transfer. Wait and retry.

### Certificate provisioned but browser shows warnings

- **Mixed content:** your Django app may be loading HTTP resources. Ensure all asset URLs use HTTPS or protocol-relative URLs.
- **Wrong domain in cert:** verify the exact domain string in Render matches what you configured in DNS (no trailing dot, no typo).
- **Intermediate certificate chain:** Render handles this automatically, but if you're behind a CDN/proxy, the proxy may need its own certificate.

### Forcing HTTPS

Render **redirects HTTP to HTTPS by default** for custom domains with valid certificates. No additional configuration needed. In Django, you can additionally set `SECURE_SSL_REDIRECT = True` for defense-in-depth, but it's not strictly required on Render.

## Official Docs

- TLS Certificates: https://render.com/docs/tls
- Custom Domains: https://render.com/docs/custom-domains