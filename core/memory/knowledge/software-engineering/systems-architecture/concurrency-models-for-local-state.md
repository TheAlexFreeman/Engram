---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [concurrency, optimistic-locking, mvcc, actor-model, version-tokens, sqlite]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - ../../ai/frontier/architectures/state-space-models.md
  - provenance-and-trust-models.md
  - ../../cognitive-science/attention/early-late-selection-models.md
  - temporal-data-modeling.md
  - schema-evolution-strategies.md
  - write-ahead-logging-and-wal-design.md
  - filesystem-atomicity-and-locking.md
  - append-only-logs-and-compaction.md
  - content-addressable-storage-and-integrity.md
  - filesystems-for-developers.md
---

# Concurrency Models for Local State

The memory system currently behaves best when one actor writes at a time. That is not a flaw. It is a concurrency model. The design question is whether to make that model explicit, where optimistic checks are enough, and where future concurrent access would need a different substrate.

## Optimistic and pessimistic concurrency solve different problems

Pessimistic control acquires a lock before work begins and holds it until commit. It is appropriate when conflicts are frequent and the protected state is expensive to recompute.

Optimistic control assumes conflicts are rare:

- read the current version
- compute a new state
- verify the version is still current at write time
- retry or fail on mismatch

The repo's version-token pattern is already optimistic concurrency control. That is a good fit for Markdown files because reads are cheap, writes are relatively small, and true simultaneous edits are uncommon.

## Version tokens are compare-and-swap for files

The deeper pattern behind version tokens is compare-and-swap:

- expected old state
- new proposed state
- apply only if the expected state still matches reality

That means version tokens are not merely "stale file detection". They are the system's semantics-aware race detector. The right implication is to use them consistently on mutable structured files, not to treat them as an optional safety belt.

## MVCC matters mainly for future derived-state databases

Multi-version concurrency control keeps several committed versions available so readers can observe a stable snapshot while a writer commits a new version.

This matters most if the system grows a SQLite derived-state database:

- readers can continue without blocking on a writer
- writers append or publish a new versioned state
- snapshot semantics remain simple

It does not mean the Markdown store itself should emulate MVCC. The cleaner design is to keep canonical files simple and let any derived SQLite index provide the multi-version read behavior.

## The actor model is the best fit for governed writes

The actor model says one owner controls a state domain and all mutation happens through message passing to that owner. In practice, the MCP server is already close to this model:

- it is the governed entry point for semantic writes
- it can serialize mutations
- it can centralize validation, batching, and commit publication

That is more important than it first sounds. If the repo adopts "single writer per worktree" as an explicit architectural rule, many difficult concurrency problems simply disappear.

This also explains why protected-tier writes should stay narrow and centralized rather than being exposed as raw file edits.

## Lock-free structures are the wrong abstraction here

Lock-free and wait-free algorithms are valuable when many threads contend on shared in-memory data. They are not the right primary abstraction for a Git-backed file repository.

Reasons:

- the bottleneck is filesystem and Git mutation, not in-memory contention
- correctness costs are high
- the actor model and optimistic compare-and-swap solve the actual problem more directly

This is useful because it narrows the design space. The repo does not need sophisticated lock-free algorithms to become robust.

## Where the boundary should be drawn

The most coherent concurrency split is:

- canonical Markdown and JSONL: single-writer actor model plus version tokens on structured files
- append-only logs and scratchpads: tolerant of concurrent append patterns with narrower invariants
- future SQLite derived state: MVCC-friendly read path

That keeps the concurrency story aligned with the actual artifact types rather than forcing one mechanism everywhere.

## Relevance to agent-memory-seed

This research strengthens several active plans:

- version-token tools should be framed as optimistic compare-and-swap, not just stale-file checks
- the MCP runtime boundary should explicitly describe itself as the single writer for governed mutations
- worktree integration should assume one writer per memory worktree and use branch or worktree isolation, not shared mutable editing, for parallel agent tasks
- any future SQLite index should be justified by MVCC-friendly derived-state reads, not by replacing the canonical file store

The core architectural takeaway is that the repository does not need general collaborative concurrency. It needs an explicit single-writer model, disciplined optimistic checks, and a cleaner boundary between canonical state and derived query state.

## Sources

- Standard database literature on optimistic locking and MVCC
- Actor-model literature from Erlang and Akka-style systems
- Existing repository plans describing version tokens and governed write boundaries
