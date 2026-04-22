---
created: '2026-04-22'
origin_session: memory/activity/2026/04/22/chat-001
source: Render official docs + community forums, researched 2026-04-22
trust: low
---

# Render Custom Domain & DNS Setup

## Adding a Custom Domain in Render

1. Go to your Render service's **Settings → Custom Domains**.
2. Click **Add Custom Domain** and enter the full domain (e.g., `demo.example.com`).
3. Render shows you the required DNS record. For subdomains, this is a **CNAME** pointing to `<service-name>.onrender.com`.
4. Add the DNS record at your registrar/DNS provider.
5. Click **Verify** in Render. If verification fails, DNS may not have propagated yet — wait a few minutes and retry.

## DNS Record Types by Domain Type

| Domain Type | Record Type | Host | Value |
|---|---|---|---|
| Subdomain (e.g., `demo.example.com`) | **CNAME** | `demo` | `<service>.onrender.com` |
| Root/apex (e.g., `example.com`) | **ANAME** or **ALIAS** | `@` | `<service>.onrender.com` |

**Important:** Not all DNS providers support ANAME/ALIAS records for root domains. If yours doesn't, use a subdomain instead or move DNS to a provider that does (e.g., Cloudflare, DNSimple).

## Key Gotchas

- **Remove conflicting AAAA records.** Render uses IPv4. Existing AAAA (IPv6) records on the same hostname can cause unexpected routing. Delete them before adding the CNAME.
- **Propagation takes time.** DNS changes can take minutes to 48 hours. Render verification will fail until propagation completes.
- **One domain per record.** Each custom domain in Render needs its own DNS record.
- **Cloudflare proxy mode.** If using Cloudflare, set the record to **DNS only** (grey cloud) during initial setup so Render can verify and provision the TLS certificate.

## Official Docs

- Custom Domains: https://render.com/docs/custom-domains
- Configuring Other DNS Providers: https://render.com/docs/configure-other-dns
- Configuring Cloudflare: https://render.com/docs/configure-cloudflare-dns