# 2026-03-06 Sync Client Mocking Docs Reorganization

## Change Context

- Start time: 2026-03-06 06:56:00 PST.
- Change time: 2026-03-06 06:56:00 PST.
- Branch: `dev`.
- Commit at start: intentionally omitted during anonymization.
- Worktree: separate source worktree used while drafting the guidance.

## Summary

Reorganized the sync and third-party integration docs into a cleaner core/reference
split.

The resulting six-document set is:

- `docs/engineering/sync-best-practices.md`
- `docs/engineering/sync-reference-patterns.md`
- `docs/engineering/api-client-best-practices.md`
- `docs/engineering/api-client-reference-patterns.md`
- `docs/engineering/third-party-mocking-best-practices.md`
- `docs/engineering/third-party-mocking-reference-patterns.md`

## Why

The earlier documentation pass had the right content, but the boundaries were still too
blurry:

- the sync core doc had grown too large and still carried client-adjacent material
- the sync reference doc mixed sync patterns and client patterns
- the mocking guide mixed generic guidance with concrete studied examples

This split makes the reading path clearer:

- use the core docs first for durable repository guidance
- use the reference docs second for anonymized case shapes and studied patterns

## Guidance Captured

- keep core sync guidance focused on normalization, discriminants, batching, overlap,
  leapfrog, deletion semantics, sparse updates, and eventual consistency
- move dedicated client-boundary guidance into its own core doc
- move client examples and client-construction references into a separate client
  reference doc
- keep the mocking core doc generic
- move concrete mock systems and test-harness details into a separate reference doc

## Related Updates

- Updated `AGENTS.md` so the instruction map points to all six docs.
- Updated `docs/engineering/style-guide.md` so the cross-cutting guidance references the
  client and mocking docs explicitly.
- Tightened the core docs again after a readback pass:
  - added a short "Start Here" summary near the top of the sync guide
  - added short start-checklists near the top of the client and mocking guides
  - made the "absence does not always mean deletion" warning more explicit
