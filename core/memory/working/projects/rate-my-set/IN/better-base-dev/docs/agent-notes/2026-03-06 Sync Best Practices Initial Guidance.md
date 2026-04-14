# 2026-03-06 Sync Best Practices Initial Guidance

## Change Context

- Start time: 2026-03-06 06:04:09 PST.
- Change time: 2026-03-06 06:04:09 PST.
- Branch: `dev`.
- Commit at start: intentionally omitted during anonymization.
- Worktree: separate source worktree used while drafting the guidance.

## Summary

Added an initial engineering document for sync workflow design:
`docs/engineering/sync-best-practices.md`.

Later in the same working session, split the sync documentation into:

- `docs/engineering/sync-best-practices.md` for generic repository-level guidance
- `docs/engineering/sync-reference-patterns.md` for anonymized reference cases and
  client-boundary examples

## Guidance Captured

- Sync design should compare normalized remote and local representations instead of raw
  source objects.
- The core model is `f(R) -> NR` and `g(H) -> NH`, where sync decisions are made from
  `NR` versus `NH`.
- Normalized shapes should be explicit, typed, deterministic, and limited to
  business-significant comparison data.
- After reviewing an internal timestamp-window API sync, documented a stronger reusable
  pattern: discriminants for candidate lookup, explicit normalization context, model
  methods on both sides of the sync boundary, and strict separation between comparison
  payload and sync metadata.
- Added a dedicated batched sync section covering deterministic remote pagination, one
  local DB query per batch, in-memory lookup mappings, and compare-before-write
  behavior, including pseudocode for simple-key and composite-key lookups.
- Added guidance for completeness/risk reduction via overlapping time-window syncs,
  bounded remote timestamp fields, and rewind cushions when resuming from previously seen
  maxima. Documented that this is source-specific confidence-building, not a proof of
  completeness.
- Clarified that sync strategy should be chosen from actual third-party API guarantees:
  strong APIs with stable IDs, usable timestamps, filter/sort support, and reliable
  pagination allow simpler strategies, while weaker APIs require more defensive overlap
  and multiple sync shapes.
- Added anonymized reference metadata for the initial sync example used while drafting
  the guide, along with a concise list of the sync strategies observed there.
- Added generic guidance for choosing a sync strategy with the human before
  implementation when integrating a new data source.
- Added generic guidance for dedicated third-party client or fetch boundaries:
  centralize auth, transport setup, pagination, and response shaping there, while
  keeping local sync decisions out of that layer.
- Added explicit guidance that local database constraints should usually enforce the same
  uniqueness assumptions as the sync discriminant.
- Added explicit guidance that most syncs should prefer eventual consistency and
  compare-before-write over default locking, only reaching for `select_for_update(...)`
  or stronger serialization when the use case clearly requires it.
- Clarified that outbound-only and bidirectional sync are intentionally out of scope for
  this document and should get separate documentation later if needed.

## Related Updates

- Added the new sync doc to the root instruction map in `AGENTS.md`.
- Added a short cross-cutting pointer in `docs/engineering/style-guide.md`.
- Added `docs/engineering/sync-reference-patterns.md` and linked it from `AGENTS.md`
  and `docs/engineering/style-guide.md`.
- Expanded `docs/engineering/sync-best-practices.md` again after reviewing an internal
  mirrored-source family sync framework.
- Representative module shapes reviewed in that pass:
  - `backend/models/synced_base.py`
  - `backend/models/catalog_items.py`
  - `backend/models/orders.py`
  - `backend/models/invoices.py`
  - `backend/ops/sync_runs.py`
  - `backend/ops/one_off_syncs.py`
  - `backend/tests/ops/test_sync_runs.py`
- Captured additional sync guidance from that mirrored-source framework:
  - mirror-snapshot sync as a complement to paired normalized-space sync
  - abstract synced-base models for a whole remote source family
  - generic model-configured sync runners
  - storing raw remote payload snapshots alongside typed extracted fields
  - retrieval timestamps as first-class sync metadata
  - minimum expected record-count sanity checks on full sweeps
  - parent-scoped sync loops for child resources
  - reusable single-record refresh logic
  - soft deletion marking and revival behavior when full sweeps prove absence
  - storage-precision-aware comparison where persistence precision matters
- Added explicit human guidance about deletion semantics:
  - if a sync can reliably guarantee a full remote sweep, absence of a lookup key can
    justify either hard deletion or, preferably, soft deletion
  - preferred pattern is to mark as deleted first, then hard-delete only after a
    source-specific retention threshold such as 3, 14, 30, 60, 90, or 180 days
  - absence from a third-party source does not always mean true deletion; some sources
    archive, compact, or otherwise stop returning records without treating them as
    deleted
- Added explicit human guidance about sparse update behavior for sync writes:
  - prefer `update_fields` for per-instance updates
  - for batch updates, group records by changed field set such as `frozenset(...)`
    and run one `bulk_update(...)` per field-set group
  - this improves write precision, consistency, and history-tooling accuracy
- Expanded `docs/engineering/sync-best-practices.md` again after reviewing an internal
  warehouse-backed mirror sync.
- Representative module shapes reviewed in that pass:
  - `backend/models/live_entities.py`
  - `backend/models/remote_records.py`
  - `backend/models/remote_contracts.py`
  - `backend/ops/remote/models_sync.py`
  - `backend/tasks/models_sync.py`
  - `backend/integrations/warehouse_fetchers.py`
  - `backend/tests/models/test_remote_sync_consistency.py`
- Captured additional sync guidance from that warehouse-backed mirror sync:
  - using a warehouse-backed remote mirror table as the sync source for a local app
    model
  - typed remote contracts that drive synchronized field lists and remote projection
  - model-level transformers for incoming cleanup and comparable local shaping
  - explicit distinction between observation freshness and data-change freshness
  - explicit clean-update versus dirty-update accounting and persistence
  - deletion marking from stale observation timestamps after a full sweep instead of
    carrying a full seen-key set through the whole run
  - separate scheduled hard-deletion tasks after model-specific `delete_after`
    thresholds
  - generic create/update callback hooks with batch context
  - grouping `bulk_update(...)` calls by `frozenset(update_field_names)` when different
    records changed different subsets of fields
  - multi-source remote merging/override before generic sync execution
- Expanded `docs/engineering/sync-best-practices.md` again after reviewing an internal
  ordered-traversal metadata sync.
- Representative module shapes reviewed in that pass:
  - `backend/models/object_tree_entries.py`
  - `backend/ops/object_tree/structures.py`
  - `backend/ops/object_tree/leapfrog.py`
  - `backend/ops/object_tree/crawling.py`
  - `backend/ops/object_tree/deletions.py`
  - `backend/ops/object_tree/discovery.py`
  - `backend/tasks/object_tree/crawling.py`
  - `backend/tests/test_object_tree_crawling.py`
- Captured additional sync guidance from that ordered-traversal sync:
  - ordered unique-key leapfrog sync as a distinct strong-API pattern
  - object-store style listings as a concrete example where deterministic key ordering and
    unique keys make streaming merge sync possible
  - deriving the local comparison stream as the latest-known row per key in matching
    order
  - exact file-level deletion detection from ordered absence in a full traversal
  - append-only create/update/delete/undelete history rows rather than in-place record
    mutation
  - reconstructing current active state from the latest row per key while filtering out
    deleted rows
  - small defensive duplicate-key safeguards even when the source is supposed to provide
    unique keys
  - generalized leapfrog pseudocode and guidance that is intentionally not tied to
    project-specific naming or semantics
- Reviewed additional client-boundary files while clarifying third-party client
  structure guidance:
  - `backend/integrations/source_client.py`
  - `backend/models/source.py`
  - `backend/ops/sync_runs.py`
  - `backend/integrations/warehouse_fetchers.py`
  - `backend/models/live_entities.py`
  - `backend/models/object_tree_entries.py`
  - `backend/ops/object_tree/crawling.py`
  - `backend/ops/object_tree/discovery.py`
- Captured additional client-boundary guidance:
  - prefer one obvious remote-client or remote-fetch boundary per source family
  - explicit HTTP APIs often justify dedicated client classes with list/detail/iterate
    methods and centralized auth/timeout/path handling
  - warehouse-backed syncs can use thin fetcher modules or model-declared fetchers
    instead of classical HTTP clients
  - mature SDK-backed sources may only need configured cached client accessors rather
    than a custom wrapper class
  - sync logic should call the client boundary, not reconstruct transport setup inline
- Reviewed additional client-testing files while expanding the reference guidance:
  - `backend/conftest.py`
  - `backend/tests/mock_systems/mock_remote_api.py`
  - `backend/tests/mock_systems/mock_remote_structure.py`
  - `backend/tests/factories/remote_records.py`
  - `backend/tests/ops/test_sync_runs.py`
  - `backend/integrations/identity_provider.py`
  - `backend/tests/integrations/test_identity_provider.py`
  - `backend/tests/sync/test_identity_sync.py`
  - `backend/integrations/partner_api_client.py`
  - `backend/tests/integrations/test_partner_api_client.py`
  - `backend/tests/integrations/test_partner_api_client_regions.py`
- Captured additional client-testing guidance:
  - block real network calls by default in tests with autouse `requests_mock` and/or
    `respx_mock`
  - keep the client boundary narrow enough that direct HTTP-boundary tests are easy to
    write
  - use `time_machine` or similar clock control for token TTL, cookie caching, and
    expiration logic
  - one reviewed example provided a full reusable mock remote system plus record-factory
    layer for sync and client testing
  - one reviewed example provided a strong identity-provider pattern: explicit
    credential objects, separate cached versus uncached token helpers, and direct
    TTL/cache tests
  - one reviewed example mainly showed the network-safety baseline and lighter direct
    client coverage
  - one reviewed example had strong direct client tests for a partner API together with
    a clearly testable auth-oriented API layer, but uneven direct coverage across all
    client boundaries
