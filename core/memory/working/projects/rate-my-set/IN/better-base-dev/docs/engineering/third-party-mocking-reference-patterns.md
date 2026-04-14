# Third-Party Mocking Reference Patterns

## Purpose

Collect concrete third-party mocking and test-harness examples distilled from prior
internal work.

This document stays intentionally pattern-heavy, but the source details are anonymized.
Keep generic repository guidance in
[Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).

## How To Use This Document

- Use this document when the generic mocking guide needs concrete examples.
- Prefer copying the underlying idea, not the exact naming or file layout.
- Treat the cases below as reusable testing archetypes, not mandatory templates.

## Navigation

- For the generic mocking playbook, go to
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).
- For client-boundary guidance, go to
  [API Client Best Practices](./api-client-best-practices.md).
- For client-boundary examples, go to
  [API Client Reference Patterns](./api-client-reference-patterns.md).
- For sync strategy guidance, go to
  [Sync Best Practices](./sync-best-practices.md).
- For concrete sync examples, go to
  [Sync Reference Patterns](./sync-reference-patterns.md).

## Case A: Network Blocking Baseline

Representative module shapes:

- `backend/conftest.py`

Patterns observed:

- repo-wide autouse `requests_mock` and `respx_mock` fixtures block accidental network
  calls
- this gives a strong baseline safety net even where a source does not yet have a rich
  dedicated mock harness

In the reviewed example behind this pattern, direct client coverage was lighter than the
repo-wide network-safety baseline.

## Case B: Stateful HTTP Mock System

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/rich_source_client.py`
- `backend/tests/mock_systems/mock_remote_api.py`
- `backend/tests/mock_systems/mock_remote_structure.py`
- `backend/tests/factories/remote_records.py`
- `backend/tests/ops/test_sync_runs.py`

Patterns observed:

- repo-wide autouse fixtures block accidental network calls
- one fixture returns a structured integration harness such as
  `MockRemoteStructure(api=..., maker=...)`
- `MockRemoteApi` is a stateful remote simulation, not a shallow endpoint stub
- the mock parses methods, paths, query params, and request bodies before responding
- unsupported request shapes raise explicit missing-mock errors
- consistency problems such as duplicate remote primary keys raise dedicated errors
- a maker layer creates realistic raw remote records and can materialize synced local
  models from the same fixture system
- sync tests vary batch size, control time, patch perf counters, and assert exact DB
  outcomes for insert, update, noop, and deletion paths

This is the strongest anonymized example of a deep reusable mock system paired with a
full sync-test harness.

## Case C: Identity API Tests Plus SDK Fake Client

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/identity_provider.py`
- `backend/tests/integrations/test_identity_provider.py`
- `backend/tests/sync/test_identity_sync.py`
- `backend/models/object_tree.py`
- `backend/ops/object_tree/crawling.py`
- `backend/tests/test_object_tree_crawling.py`

Patterns observed:

- repo-wide autouse fixtures block real `requests` and `httpx` traffic
- direct identity-provider tests freeze time, clear token caches, and patch the TTL
  cache timer so frozen time controls cache expiration
- identity-provider tests cover both cached and uncached token flows across multiple
  application credentials
- higher-level sync tests reuse the same mocked identity-provider endpoints
- storage-crawling tests patch the SDK constructor at the boundary where the crawler
  builds the client
- the fake SDK client stores endpoint and credential inputs so tests can assert the
  construction contract
- the fake exposes a paginator that emits deterministic pages, truncation flags, and
  continuation tokens

This is the clearest anonymized example of combining strong HTTP-boundary tests with
strong SDK-boundary fake clients.

## Case D: Stateful Partner API Mock

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/partner_api_client.py`
- `backend/tests/mock_partner_api.py`
- `backend/tests/integrations/test_partner_api_client.py`
- `backend/tests/integrations/test_partner_api_client_regions.py`
- `backend/integrations/identity_api.py`
- `backend/tests/ops/test_bulk_invitations.py`

Patterns observed:

- autouse HTTP-blocking fixtures provide the repo-wide safety baseline
- `MockPartnerApi` owns route registration through `setup_mocking()`
- the mock keeps internal state maps for remote entities instead of returning fixed
  canned payloads
- responders parse request JSON, allocate IDs, mutate remote state, and return
  realistic HTTP responses
- direct client tests clear auth caches between runs and use `time_machine` to verify
  cookie refresh windows
- tests assert both safe and verbose error rendering so secrets stay out of normal
  exception strings
- separate tests validate config-based client construction for different regions or
  tenants

This is the strongest anonymized example of direct client testing around auth, caching,
config selection, and error rendering.

## Compare And Contrast

Case A emphasizes:

- network blocking as a baseline safety pattern

Case B emphasizes:

- a fully stateful remote mock system
- one fixture surface for mock API plus data makers
- full sync-flow assertions against that harness

Case C emphasizes:

- time-aware identity-provider client tests
- patching SDK constructors directly
- fake paginators for storage-style APIs

Case D emphasizes:

- stateful API mocks with route registration helpers
- direct client tests around auth, caching, config selection, and error rendering
