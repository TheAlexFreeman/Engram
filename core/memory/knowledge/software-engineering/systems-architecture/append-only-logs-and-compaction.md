---

source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [logs, compaction, lsm, kafka, cqrs, access-jsonl, archival, summaries]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - filesystem-atomicity-and-locking.md
  - crdts-and-collaborative-text.md
  - filesystems-for-developers.md
  - concurrency-models-for-local-state.md
---

# Append-Only Logs, Compaction, and Materialized Summaries

`ACCESS.jsonl` is already a log-structured subsystem. Every retrieval appends a fact, and later processes are supposed to summarize or archive those facts. The current system therefore does not need a new abstraction so much as a clearer one: treat ACCESS logging as an append-only event stream, and treat summary updates as compaction and materialization.

## Append-only logs optimize writes and defer organization

Append-first systems trade one problem for another.

Benefits:

- appends are simple and cheap
- writes avoid in-place mutation races
- history stays auditable

Costs:

- reads become more expensive over time
- duplicate or superseded facts accumulate
- some secondary index or summary becomes necessary

That trade-off is exactly what the repo is now experiencing. Logging reads is easy. Interpreting 100+ plan entries is not.

## LSM trees show the standard pattern: hot log now, compacted tables later

Log-Structured Merge trees use an in-memory write buffer, flush immutable files, and compact them into more query-friendly tables over time. The important lesson is not the exact data structure. It is the lifecycle:

- small, recent write path stays cheap
- immutable segments accumulate
- background compaction rewrites many old entries into fewer query-efficient structures

That is a strong analogy for ACCESS handling:

- hot segment: current `ACCESS.jsonl`
- immutable history: rotated archive segments
- query-friendly state: `SUMMARY.md` usage sections or future derived indexes

## Kafka compaction distinguishes retention from state derivation

Kafka makes an especially useful distinction between:

- time-based retention: discard old segments after a policy window
- log compaction: keep the latest effective value per key while still preserving an append-only write path

The repo wants the second idea more than the first. For ACCESS, the goal is not simply to throw away old reads. The goal is to retain the raw event stream while deriving smaller, decision-friendly aggregates such as:

- file retrieval counts
- mean helpfulness
- co-retrieval groups
- stale or low-value file flags

That means aggregation should behave like compaction into materialized state, not like destructive cleanup.

## Raw events should remain the canonical audit trail

The event-sourcing lesson is straightforward:

- raw access events are canonical history
- summaries are derived views
- derived views can be rebuilt

That suggests two concrete rules for agent-memory-seed:

1. never rewrite or normalize old ACCESS events in place
2. perform all cleanup by rotation or archival, not mutation

This is the strongest argument against any design that treats summary files as the only enduring output of aggregation.

## Rotation policy matters as much as aggregation logic

The current documentation mentions `ACCESS.archive.jsonl` but does not define a practical rotation strategy. Production log systems almost always define both a hot file and a segmented archive.

For this repo, the most natural policy is:

- keep one hot `ACCESS.jsonl` per folder for new entries
- when aggregation runs, move processed entries into a dated archive segment such as `ACCESS.archive.2026-03.jsonl`
- optionally maintain a tiny manifest or metadata block describing the last aggregation time and segment count

That is better than a single ever-growing `ACCESS.archive.jsonl` because it keeps archival scans bounded and makes per-period inspection easier.

## Aggregation should produce materialized views, not just reports

Compaction is valuable only if it leaves behind a faster read path.

For this repository, the materialized outputs should be things like:

- updated "Usage patterns" sections in folder `SUMMARY.md` files
- cluster or co-retrieval summaries
- backlog metrics for overdue aggregation
- maybe a future SQLite derived-state index

The main risk in the current semantic-tools plan is that `memory_run_aggregation` is described partly as a reporting tool. The stronger design is for it to own the full compaction cycle:

- analyze hot events
- update materialized summaries
- archive processed entries into immutable segments
- reset the hot log to empty

## Low-signal events should be separated without losing auditability

The access-log plan proposes routing low-helpfulness events to `ACCESS_SCANS.jsonl`. That can be consistent with append-only design if the rule is interpreted carefully.

Good version:

- keep scans as raw immutable events
- exclude them from primary maturity calculations by default
- preserve them as audit data that can still be reprocessed later

Bad version:

- silently discard them or mix them into the main archival story without a clear schema boundary

The distinction matters because event systems age well only when their data classes remain explicit.

## Relevance to agent-memory-seed

This research implies several design corrections for active plans:

- aggregation should be treated as log compaction plus materialized-view refresh, not a one-off analytical report
- archive handling should rotate into dated immutable segments, not a single monolithic archive file
- session-health tooling should inspect the hot log and report aggregation backlog, rather than scanning the entire historical archive every time
- summary sections should be treated as rebuildable views derived from ACCESS events, not hand-maintained prose

The architectural takeaway is that ACCESS is already an event stream. The missing work is checkpointing, rotation, and materialized-view discipline.

## Sources

- Literature and documentation on LSM trees and compaction
- Kafka documentation on retention versus log compaction
- Event-sourcing and CQRS design literature