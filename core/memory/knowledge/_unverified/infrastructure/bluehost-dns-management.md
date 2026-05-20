---
created: '2026-04-22'
origin_session: memory/activity/2026/04/22/chat-001
source: external-research
trust: low
---

# Bluehost DNS Management — Subdomains & CNAME Records

## Adding a CNAME Record for a Subdomain

1. Log into Bluehost → left nav → **Hosting** → **Settings**.
2. Locate the domain → click **Manage** → select **DNS** from the dropdown.
3. Scroll to **CNAME (Alias) Records** → click **Add Record**.
4. Fill in:
   - **Host Record:** the subdomain prefix only (e.g., `demo` for `demo.example.com`)
   - **Points To:** the target hostname (e.g., `myapp.onrender.com`)
   - **TTL:** leave at default (14400 seconds / 4 hours is typical)
5. Click **Save**.

## Propagation

Bluehost warns that DNS changes can take **up to 48 hours** to fully propagate, though in practice CNAME records often resolve within 15–60 minutes.

## Gotchas Specific to Bluehost

- **Bluehost creates default A/AAAA records** for new subdomains that point to their own servers. If you create a subdomain via the "Subdomains" tool *before* adding the CNAME, you may end up with conflicting records. Check the DNS zone for stale A/AAAA entries on the subdomain and delete them.
- **cPanel vs. new Bluehost UI:** Older Bluehost accounts may use cPanel's Zone Editor instead of the Bluehost dashboard. The fields are the same; navigation differs.
- **Bluehost's "Subdomains" tool** creates a directory on the server and an A record — this is for Bluehost-hosted content. If you only need to point the subdomain externally, skip that tool entirely and go straight to DNS management to add the CNAME.

## Official Docs

- How to Add a CNAME Record: https://www.bluehost.com/blog/how-to-add-a-cname-record/
- CNAME Help: https://my.bluehost.com/cgi/help/cname
- Subdomains: https://www.bluehost.com/help/article/subdomains
- DNS Management: https://www.bluehost.com/help/article/dns-management-add-edit-or-delete-dns-entries