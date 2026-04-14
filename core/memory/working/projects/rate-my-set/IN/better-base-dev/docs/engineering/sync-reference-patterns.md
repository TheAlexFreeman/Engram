# Sync Reference Patterns

## Purpose

Collect concrete sync examples distilled from prior internal work.

This document stays intentionally pattern-heavy, but the source details are anonymized.
Keep generic repository guidance in
[Sync Best Practices](./sync-best-practices.md).

## How To Use This Document

- Use this document when the generic sync guide needs a more concrete mental model.
- Prefer copying the underlying idea, not the exact naming or file layout.
- Treat the cases below as reusable sync archetypes, not mandatory templates.

## Navigation

- For the generic sync playbook, go to
  [Sync Best Practices](./sync-best-practices.md).
- For client-boundary guidance, go to
  [API Client Best Practices](./api-client-best-practices.md).
- For client-boundary examples, go to
  [API Client Reference Patterns](./api-client-reference-patterns.md).
- For third-party testing guidance, go to
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).
- For third-party mock-system examples, go to
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md).

## Case A: Timestamp-Window Comparison Sync

Representative module shapes:

- `backend/integrations/source_api.py`
- `backend/models/source_records.py`
- `backend/ops/sync/entity_events.py`
- `backend/ops/sync/entity_reports.py`
- `backend/ops/sync/entity_agents.py`
- `backend/ops/sync/entity_events_by_updated_at.py`
- `backend/tests/ops/test_entity_syncs.py`

Patterns observed:

- explicit remote and local normalization into a shared comparison space
- explicit discriminants before full equality comparison
- batched fetch-and-compare with one local lookup query per remote batch
- simple-key lookups and composite-key `Q(...) | Q(...)` lookup unions
- deterministic remote ordering and pagination
- overlapping timestamp-window syncs
- rewind cushions for resuming from prior maxima

This is the clearest anonymized example of the normalized comparison-space model plus
practical batched sync loops.

## Case B: Mirrored-Source Family Sync

Representative module shapes:

- `backend/models/synced_base.py`
- `backend/models/catalog_items.py`
- `backend/models/catalog_attributes.py`
- `backend/models/orders.py`
- `backend/models/invoices.py`
- `backend/ops/sync_runs.py`
- `backend/ops/one_off_syncs.py`
- `backend/ops/order_syncs.py`
- `backend/tests/ops/test_sync_runs.py`

Patterns observed:

- mirror-snapshot sync as a complement to narrow normalized comparison
- abstract synced-base models for one remote source family
- generic model-configured sync runners
- raw remote payload storage alongside typed extracted fields
- metadata such as `first_synced_at` and `last_synced_with_changes_at`
- minimum expected record-count sanity checks
- parent-scoped syncs for child resources
- single-record refreshes that reuse the same sync logic
- soft deletion marking and revival after full sweeps
- storage-precision-aware comparison

This is the strongest anonymized example of a durable mirrored-source sync framework.

## Case C: Ordered-Key Traversal Sync

Representative module shapes:

- `backend/models/object_tree_entries.py`
- `backend/ops/object_tree/structures.py`
- `backend/ops/object_tree/leapfrog.py`
- `backend/ops/object_tree/crawling.py`
- `backend/ops/object_tree/deletions.py`
- `backend/ops/object_tree/discovery.py`
- `backend/tasks/object_tree/crawling.py`
- `backend/tests/test_object_tree_crawling.py`

Patterns observed:

- ordered unique-key leapfrog sync
- deterministic remote ordering over object-store style listings
- deriving the local stream as the latest-known row per key
- exact delete and undelete detection from ordered absence in a full traversal
- append-only create, update, delete, and undelete history rows
- reconstructing current state from latest rows instead of mutating one record in place
- defensive duplicate-key checks even when the source should be unique

This is the clearest anonymized example of leapfrog-style ordered merge sync.

## Case D: Warehouse-Backed Mirror Sync

Representative module shapes:

- `backend/models/live_entities.py`
- `backend/models/remote_records.py`
- `backend/models/remote_contracts.py`
- `backend/ops/remote/models_sync.py`
- `backend/tasks/models_sync.py`
- `backend/integrations/warehouse_fetchers.py`
- `backend/tests/models/test_remote_sync_consistency.py`

Patterns observed:

- syncing from a warehouse-backed remote mirror table into a local app model
- typed remote contracts that drive synchronized field lists and projection
- model-level transformers for incoming cleanup and comparable local shaping
- explicit split between observation freshness and data-change freshness
- clean-update versus dirty-update accounting
- deletion marking based on stale observation timestamps after a full sweep
- delayed hard deletion after a model-specific retention window
- grouped `bulk_update(...)` calls by `frozenset(update_field_names)`
- merged or overridden remote views before the generic sync engine runs

This is the strongest anonymized example of generic sync infrastructure over a mirrored
warehouse-backed remote source.

## Compare And Contrast

Case A emphasizes:

- paired normalized comparison-space mapping
- batched lookup-map sync
- overlapping windows
- rewind cushions

Case B emphasizes:

- mirror-snapshot local models
- generic multi-model sync framework reuse
- parent-scoped syncs
- soft deletion after full sweeps

Case C emphasizes:

- ordered unique-key leapfrog sync
- exact absence detection from ordered traversal
- append-only delete and undelete history

Case D emphasizes:

- warehouse-backed remote mirrors
- typed remote contracts
- observation-versus-change freshness tracking
- staleness-based deletion marking
- sparse grouped bulk updates
