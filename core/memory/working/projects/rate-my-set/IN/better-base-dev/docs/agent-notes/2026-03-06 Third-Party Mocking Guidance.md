# 2026-03-06 Third-Party Mocking Guidance

## Change Context

- Start time: 2026-03-06 06:56:00 PST.
- Change time: 2026-03-06 06:56:00 PST.
- Branch: `dev`.
- Commit at start: intentionally omitted during anonymization.
- Worktree: separate source worktree used while drafting the guidance.

## Summary

Added a dedicated engineering document for thoroughly mocking third-party systems:
`docs/engineering/third-party-mocking-best-practices.md`.

Also linked that document from:

- `AGENTS.md`
- `docs/engineering/style-guide.md`

## Guidance Captured

- Prefer one explicit client or fetch boundary per third-party source family.
- Block real outbound traffic in tests by default.
- Test the client boundary directly, then separately test the sync, crawl, or workflow
  layer that consumes it.
- For non-trivial integrations, prefer reusable stateful mock systems over scattered
  one-off endpoint stubs.
- Pair stateful remote mocks with factory or maker helpers when sync tests need large
  volumes of realistic remote data.
- Use structured fixtures to centralize `respx_mock`, time control, settings, cache
  clearing, and log capture.
- Patch SDK constructors at the boundary and return fake clients that simulate the
  methods and paginator behavior the production code actually depends on.
- Assert auth inputs, request shaping, cache refresh behavior, and safe error rendering,
  not just returned payloads.
- Prefer explicit missing-mock failures when production behavior outgrows the test
  harness.

## Reference Patterns Reviewed

### Stateful HTTP Mock System

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/rich_source_client.py`
- `backend/tests/mock_systems/mock_remote_api.py`
- `backend/tests/mock_systems/mock_remote_structure.py`
- `backend/tests/factories/remote_records.py`
- `backend/tests/ops/test_sync_runs.py`

Key notes:

- `MockRemoteApi` is the strongest reviewed example of a stateful HTTP mock system.
- A structured fixture such as `MockRemoteStructure(api=..., maker=...)` keeps the
  remote fixture surface ergonomic and consistent.
- The sync tests are strongest when they vary batch sizes, control time, and assert
  exact DB effects.

### Stateful Partner API Mock

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/partner_api_client.py`
- `backend/tests/mock_partner_api.py`
- `backend/tests/integrations/test_partner_api_client.py`
- `backend/tests/integrations/test_partner_api_client_regions.py`

Key notes:

- A route-registering mock class such as `MockPartnerApi` is a strong direct-client
  harness for auth, caching, and error handling.
- The strongest direct client tests verify cache refresh windows, safe error strings,
  and config-based client construction.

### Identity API Tests Plus SDK Fake Client

Representative module shapes:

- `backend/conftest.py`
- `backend/integrations/identity_provider.py`
- `backend/tests/integrations/test_identity_provider.py`
- `backend/tests/sync/test_identity_sync.py`
- `backend/models/object_tree.py`
- `backend/ops/object_tree/crawling.py`
- `backend/tests/test_object_tree_crawling.py`

Key notes:

- Identity-provider tests are a good example of cache-aware time control.
- Storage-crawling tests are a good example of patching the SDK constructor and
  returning a fake paginator instead of flattening away remote behavior.
