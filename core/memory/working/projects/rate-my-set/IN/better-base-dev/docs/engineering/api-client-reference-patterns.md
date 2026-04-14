# API Client Reference Patterns

## Purpose

Collect concrete client-boundary examples distilled from prior internal work.

This document stays intentionally pattern-heavy, but the source details are anonymized.
Keep generic repository guidance in
[API Client Best Practices](./api-client-best-practices.md).

## How To Use This Document

- Use this document when the generic client guide needs concrete examples.
- Prefer copying the underlying idea, not the exact naming or file layout.
- Treat the cases below as reusable client-boundary archetypes, not mandatory templates.

## Navigation

- For the generic client playbook, go to
  [API Client Best Practices](./api-client-best-practices.md).
- For sync strategy guidance, go to
  [Sync Best Practices](./sync-best-practices.md).
- For concrete sync examples, go to
  [Sync Reference Patterns](./sync-reference-patterns.md).
- For third-party testing guidance, go to
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).
- For third-party mock-system examples, go to
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md).

## Case A: Small Explicit HTTP Client

Representative module shapes:

- `backend/integrations/source_client.py`
- `backend/models/source.py`
- `backend/ops/sync/entity_events.py`
- `backend/ops/sync/entity_reports.py`
- `backend/conftest.py`

Patterns observed:

- `RemoteApiClient` is a dedicated HTTP client class
- it owns base-URL formation, auth header construction, default timeouts, and path
  normalization
- it exposes a small surface such as `get(...)`, `request(...)`,
  `prepare_request_args(...)`, and `make_request_from_prepared_args(...)`
- the prepared-args object gives one explicit transport contract that is easy to inspect
- `source.client` or an equivalent accessor keeps acquisition easy for sync code
- repo-wide autouse HTTP-blocking fixtures provide the network-safety baseline

In the reviewed example behind this pattern, the client boundary itself had less direct
coverage than the higher-level sync code.

## Case B: Rich Sync-Facing HTTP Client

Representative module shapes:

- `backend/integrations/rich_source_client.py`
- `backend/ops/sync_runs.py`
- `backend/ops/one_off_syncs.py`
- `backend/ops/order_syncs.py`
- `backend/ops/invoice_syncs.py`
- `backend/conftest.py`

Patterns observed:

- `RichRemoteClient` is a dedicated HTTP client class with a wider sync-facing surface
- it wraps repetitive response-envelope parsing in typed response wrappers
- it exposes ergonomic methods such as `get_list(...)`, `get_detail(...)`, and
  `iterate_all(...)`
- it centralizes auth parameter handling, SSL context reuse, timeout defaults, cursor
  handling, and awkward request-body shaping
- it can also own a small number of source-specific write helpers when centralization
  clearly improves consistency
- the repo blocks accidental `requests` and `httpx` traffic by default

This is the strongest anonymized example of a rich dedicated API client with a clean
sync-facing surface.

## Case C: SDK Accessor Plus Explicit Auth Clients

Representative module shapes:

- `backend/models/object_tree.py`
- `backend/ops/object_tree/crawling.py`
- `backend/ops/object_tree/discovery.py`
- `backend/ops/object_tree/leapfrog.py`
- `backend/integrations/identity_provider.py`
- `backend/tests/integrations/test_identity_provider.py`
- `backend/tests/sync/test_object_tree_sync.py`
- `backend/conftest.py`

Patterns observed:

- the storage-style source uses configured SDK accessors such as `resource.sdk_client`
  or `sync_runner.sdk` instead of a custom wrapper class
- that boundary still owns endpoint derivation, credentials, and SDK config
- the same codebase also has explicit identity-provider client classes such as
  `RegularWebAppClient` and `MachineToMachineClient`
- shared credential objects keep client construction explicit
- token acquisition is split into cached and uncached helpers
- direct identity-client tests use `respx_mock` and `time_machine` to verify cache
  behavior

This is the strongest anonymized example of mixing SDK-backed client boundaries with
focused explicit auth clients.

## Case D: Fetch Contract Plus Specialized API Clients

Representative module shapes:

- `backend/models/live_entities.py`
- `backend/integrations/warehouse_fetchers.py`
- `backend/ops/remote/models_sync.py`
- `backend/integrations/identity_api.py`
- `backend/integrations/partner_api_client.py`
- `backend/tests/integrations/test_partner_api_client.py`
- `backend/tests/integrations/test_partner_api_client_regions.py`
- `backend/conftest.py`

Patterns observed:

- the sync uses a fetch-boundary contract rather than a classic HTTP client class
- the remote boundary is a thin fetcher function or model-level `remote_fetcher`
- that fetcher owns ordering, projection, test filtering, and chunking
- the same codebase also has explicit client layers for other API-style integrations
- the auth-oriented client layer separates authentication and management concerns, with
  explicit token caching and retry behavior
- the partner-API tests show strong direct client testing around auth cookies, config
  selection, and error behavior

This is the strongest anonymized contrast case showing that a client boundary can
legitimately be a fetch contract when the transport is already the ORM or warehouse
layer.

## Compare And Contrast

Case A emphasizes:

- a small explicit HTTP client class
- prepared request objects
- `source.client` acquisition

Case B emphasizes:

- a rich dedicated HTTP client class
- typed response wrappers
- pagination and awkward write-shape helpers in one place

Case C emphasizes:

- configured SDK-client accessors
- explicit auth client classes
- time-controlled client tests for token caching

Case D emphasizes:

- fetch-boundary contracts for warehouse-backed syncs
- explicit auth and partner-API client layers for API-style integrations
- strong client-construction and client-testing patterns even when not every client has
  identical direct coverage
