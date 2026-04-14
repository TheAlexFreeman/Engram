# Sync Best Practices

## Purpose

Document the repository-level approach for synchronizing remote data into local data in
a way that stays explicit, comparable, and safe to evolve.

## Scope

This document covers inbound remote-to-local synchronization.

That includes cases where the remote side is:

- an HTTP API
- an SDK-backed external system
- a warehouse-backed mirror table
- another durable remote read surface

Outbound-only and bidirectional sync are intentionally out of scope for now.
If repository guidance is added for those later, it should live in a separate document.

## Navigation

- If you want concrete examples and studied repos, go to
  [Sync Reference Patterns](./sync-reference-patterns.md).
- If you want client-boundary guidance, go to
  [API Client Best Practices](./api-client-best-practices.md).
- If you want concrete client examples, go to
  [API Client Reference Patterns](./api-client-reference-patterns.md).
- If you want third-party testing guidance, go to
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md).
- If you want concrete third-party mock-system examples, go to
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md).

## Start Here

If you are adding or revisiting a sync, keep these five points front and center:

- choose the strategy with the human based on the source's real guarantees
- normalize remote and local records into a shared comparison space before diffing
- make the discriminant explicit and usually enforce it in the local DB
- default to one remote fetch plus one local query per batch, then compare before write
- treat completeness and deletion semantics as source-specific; absence does not always
  mean deletion

## Choose The Sync Strategy With The Human

When adding a new data source, do not jump straight into implementation.

Work with the human to narrow the sync shape first.

The core questions are:

- what does the remote system actually guarantee about ordering, filtering, pagination,
  and timestamps
- what does the local mirror need to mean
- how complete does the sync need to be
- how much staleness is acceptable
- what should absence mean for this source
- what batch size, overlap, retry, and repair behavior are operationally reasonable

The goal is not to choose the fanciest strategy.
The goal is to choose the simplest strategy that is defensible for that source and that
use case.

## Core Model

When synchronizing, do not compare raw source objects directly.

Instead, normalize both sides into a shared comparison space:

- Remote data: `R`
- Local data: `H`
- Remote normalization: `f(R) -> NR`
- Local normalization: `g(H) -> NH`

The important comparison is `NR` versus `NH`, not `R` versus `H`.

## Core Rules

- Keep `f(...)` and `g(...)` separate.
- Normalize early, before sync decisions are made.
- Compare only normalized shapes when deciding whether records match or differ.
- Keep normalized fields limited to business-significant comparison data.
- Prefer deterministic normalization.
- Fail fast when required source data cannot be normalized cleanly.
- Keep sync metadata out of normalized equality.

## Normalized Shape Expectations

Prefer small explicit normalized records made from ordinary Python values.

Typical examples:

- `str`
- `int`
- `bool`
- `Decimal`
- `date`
- timezone-aware `datetime`
- `UUID`
- `None`
- small tuples, lists, or dictionaries when they are genuinely part of the compared
  shape

In many cases, `NR` can be an `attrs` value object, typed dict, or similarly explicit
typed record.

## Identity, Comparison Payload, And Sync Metadata

Separate these concerns clearly:

- discriminant or identity:
  the smallest stable key used to find the candidate local record
- normalized comparison payload:
  the business-significant fields used to decide whether a change exists
- sync metadata:
  local bookkeeping such as sync timestamps, counters, or deletion markers

Do not let sync metadata participate in normalized equality.

## Discriminants And Local Constraints

Before comparing full normalized payloads, identify which local record is the candidate
match for the remote record.

That discriminant might be:

- one remote primary key
- one source-scoped remote key
- one composite business key
- one time-windowed or source-scoped composite key

If the sync depends on a discriminant being unique, the local database should usually
enforce that too.

Typical examples:

- `unique=True` on one remote key field
- `UniqueConstraint` on `(source_id, remote_pk)`
- `UniqueConstraint` on a composite business key
- check constraints when source-specific invariants matter

Do not rely only on application code to preserve uniqueness assumptions that the sync
layer depends on.

## Context-Dependent Normalization

Sometimes `f(R)` cannot be computed from the raw remote record alone.

Normalization may need:

- local lookup mappings
- source-specific configuration
- related-record enrichment
- rename rules
- derived-field rules

When that happens, pass an explicit context object into normalization rather than
hiding lookups inside unrelated sync code.

## Default Sync Shape: Batched Fetch And Compare

For many third-party sources, the default shape should be:

1. Fetch the remote data in deterministic order with pagination.
2. Process one remote batch at a time.
3. Derive one lookup key per remote record.
4. Do one local DB query for the whole batch.
5. Build an in-memory mapping from lookup key to local instance.
6. Compare remote and local records one by one in normalized space.
7. Insert, update, or noop based on the normalized comparison.

The durable principle is:

- one remote fetch per batch
- one local query per batch
- compare before write

## Batched Lookup Guidance

For a simple primary key, use a single query shape such as `pk__in`.

For composite or source-scoped keys, derive a key object or tuple and use one query that
retrieves the whole candidate set for the batch.

That may be:

- one `Q(...) | Q(...) | Q(...)` union
- one reduced OR chain
- one other query shape that still preserves the "one local query per batch" rule

Then build an in-memory lookup mapping from discriminant to instance.

## Pseudocode

```python
for remote_batch in remote_client.iterate_all(ordering="deterministic", limit=500):
    lookup_keys = [derive_lookup_key(r) for r in remote_batch]

    existing_instances = fetch_existing_instances_for_batch(lookup_keys)
    existing_by_key = {derive_lookup_key_from_here(h): h for h in existing_instances}

    for remote_record in remote_batch:
        key = derive_lookup_key(remote_record)
        existing = existing_by_key.get(key)

        normalized_remote = normalize_remote(remote_record)
        normalized_here = (
            None if existing is None else normalize_here(existing)
        )

        if existing is None:
            insert_from_remote(remote_record, normalized_remote)
            continue

        if normalized_remote == normalized_here:
            mark_no_change(existing)
            continue

        update_from_remote(existing, remote_record, normalized_remote)
```

## Compare Before Write

Do not save or update records that have not meaningfully changed.

That matters because:

- overlapping sweeps become affordable
- eventual consistency becomes cheaper
- local writes stay smaller
- history tooling becomes more accurate

## Coverage Is Source-Specific

Completeness depends on the actual third-party source.

Start by asking what the source really guarantees:

- consistently increasing IDs
- usable `created_at` or `updated_at` fields
- server-side filtering
- deterministic sorting
- reliable pagination

Strong sources allow simpler syncs.
Weak sources require more defensive overlap, more repair passes, or multiple sync
shapes.

## Overlapping Time-Window Strategy

If the source has a reasonably bounded timestamp field such as `created_at` or
`updated_at`, a practical strategy is to run overlapping time-window sweeps.

Examples:

- one sync starting 3 hours back
- one sync starting 3 days back
- one sync starting 14 days back

The overlap is there to reduce the risk of missing records due to source delay,
pagination weirdness, or timestamp edge cases.

This works well when compare-before-write turns repeated overlap into mostly `no_change`.

## Rewind Cushions And Checkpoints

When resuming from a previously seen maximum timestamp or similar checkpoint, do not
resume exactly at the last seen value.

Resume with a rewind cushion.

Advance the stored checkpoint only after the relevant writes for that portion of the run
have completed durably enough for the use case.

The exact persistence model is source-specific, but the durable rule is:

- do not advance the cursor before the work it represents is safely handled

## Strong-API Pattern: Ordered Unique-Key Leapfrog

If the remote source gives you:

- a unique ordered key
- deterministic listing order
- the ability to traverse the full keyspace in that order

then another useful sync shape is leapfrog-style merge comparison.

That pattern walks the remote stream and the local stream in matching key order and
classifies each step as:

- create
- update
- delete or mark deleted
- no change

This is especially effective when the source exposes an ordered unique key such as a
storage object key.

## Mirror-Snapshot Pattern

Some syncs are better modeled as a local mirror of the remote payload rather than only a
narrow normalized comparison record.

That pattern typically includes:

- raw remote payload snapshots
- typed extracted fields
- sync metadata such as first seen, last seen, and last changed timestamps
- generic per-model sync framework reuse

This is useful when the local system needs to preserve a fairly faithful remote mirror
for later workflows.

## Parent-Scoped And Single-Record Syncs

Not every sync is one flat top-level sweep.

Useful additional shapes include:

- parent-scoped syncs for child resources
- one-off repair syncs for one remote record
- single-record refreshes that reuse the same normalization and comparison logic as the
  main sync

Do not fork separate comparison rules for one-off repair paths unless the source truly
requires it.

## Deletion Guidance

Deletion behavior must follow source semantics and user intent.

Absence does not always mean deletion.

That point is important enough to treat as a default warning:

- do not equate "not returned in this sync" with "safe to delete locally" unless the
  sync shape and source semantics support that conclusion

Some third-party systems:

- truly delete records
- archive them
- compact old data
- stop returning them for performance reasons

Only treat absence as deletion when the sync shape gives enough confidence for that
source.

## Preferred Deletion Shape

If a sync can reliably guarantee a full remote sweep, missing lookup keys can justify a
local delete decision.

Even there, prefer to start from:

- soft-delete first
- retain for a source-specific threshold
- hard-delete later only if the source semantics and product intent still support it

The preferred default is:

1. mark the local record as deleted
2. keep it for a source-specific threshold
3. hard-delete later if it still has not reappeared

Common thresholds might be 3, 14, 30, 60, 90, or 180 days, but the real value should be
source-specific.

## Sparse Updates

When updating synced records, prefer explicit sparse writes.

In Django terms, that usually means:

- `update_fields` for per-instance saves
- `bulk_update(...)` for grouped batch updates

This keeps writes smaller, makes field changes more explicit, and tends to improve
history-tooling accuracy.

## Group Bulk Updates By Changed Field Set

When different records changed different subsets of fields, group them by the set of
changed fields and run one `bulk_update(...)` per group.

Using `frozenset(...)` keys for the changed field names is a practical pattern for that.

## Pseudocode For Grouped Sparse Updates

```python
updates_by_field_set: dict[frozenset[str], list[MyModel]] = {}

for instance, remote_record in pairs_to_update:
    changed_field_names = compute_changed_field_names(instance, remote_record)
    changed_field_set = frozenset(changed_field_names)

    if not changed_field_set:
        continue

    apply_changes(instance, remote_record, changed_field_names)
    updates_by_field_set.setdefault(changed_field_set, []).append(instance)

for changed_field_set, instances in updates_by_field_set.items():
    MyModel.objects.bulk_update(
        instances,
        fields=sorted(changed_field_set),
        batch_size=500,
    )
```

## Eventual Consistency Before Locking

Most sync systems should default to eventual consistency.

That is especially true when the design already includes:

- compare-before-write
- overlapping or repeated sweeps
- idempotent create and update behavior
- durable local uniqueness constraints

Do not add row locking or stronger serialization by default.

Only reach for tools such as `select_for_update(...)` or serialized runners when the
specific source semantics or local side effects make them clearly necessary.

## Related Docs

- Concrete sync examples:
  [Sync Reference Patterns](./sync-reference-patterns.md)
- Generic client-boundary guidance:
  [API Client Best Practices](./api-client-best-practices.md)
- Concrete client-boundary examples:
  [API Client Reference Patterns](./api-client-reference-patterns.md)
- Generic third-party mocking guidance:
  [Third-Party Mocking Best Practices](./third-party-mocking-best-practices.md)
- Concrete third-party mocking examples:
  [Third-Party Mocking Reference Patterns](./third-party-mocking-reference-patterns.md)

## Initial Heuristic

When the sync design feels unclear, start by asking:

1. What is the smallest typed shape that represents the business-significant meaning of a
   record?
2. What should `f(R)` return for the remote system?
3. What should `g(H)` return for local storage?
4. If two records mean the same thing, would their normalized forms be equal?

If that last answer is not clear, the normalization model is probably not finished yet.
