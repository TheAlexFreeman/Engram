---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [wal, durability, sqlite, postgres, staging, transactions, rollback]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - ../../self/_archive/2026-03-22-plan-schema-and-activity-logging-design.md
  - ../testing/black-box-test-design.md
  - ../../cognitive-science/memory/reconsolidation-agent-design-implications.md
---

# Write-Ahead Logging and WAL-Oriented Write Design

Write-ahead logging is the standard answer to a storage problem that also appears in this repository: how do you publish a new state safely when the operation spans more than one low-level write. The core WAL rule is simple: record the intended change in a durable intermediate form before publishing the final state. Recovery then becomes replay from that intermediate record rather than guesswork.

## The WAL invariant

The invariant is "log before apply".

In a traditional database that means:

- describe the transaction in the WAL
- flush the WAL to durable storage
- apply the transaction to the main data pages later
- on crash, replay committed WAL records that were not yet checkpointed into the main store

The reason this pattern is universal is that it separates two concerns:

- commit visibility
- physical reorganization of durable state

That separation matters here because the repo already has multi-file operations whose logical commit point should be one thing even if several files were staged before it.

## Checkpoints and recovery are part of the design, not an afterthought

A WAL system needs three pieces, not one:

1. an append path for intended changes
2. a checkpoint path that folds those changes into the durable base state
3. a recovery rule for restart after interruption

Without checkpointing, the log grows forever. Without recovery, the log is just extra I/O. For agent-memory-seed, this framing maps directly onto ACCESS aggregation and any future staged write batches.

## SQLite WAL mode is the clearest local-file reference model

SQLite's WAL mode is useful because it shows how a local file-backed system can support concurrency without abandoning simple files.

Important pieces:

- the main database file remains the stable checkpointed state
- new writes land in a `-wal` file
- a `-shm` shared-memory index helps readers find the right version efficiently
- many readers can continue using a stable snapshot while one writer appends to the WAL
- checkpoints copy committed pages from the WAL back into the main database

Why this matters for this repo:

- it is the right mental model for a future derived-state SQLite index
- it shows that concurrency-friendly reads usually come from separating canonical state from append-only transient state
- it reinforces that checkpoint policy is a first-class operational choice, not just an implementation detail

## PostgreSQL WAL adds the production-scale version of the same story

PostgreSQL uses WAL segments identified by log sequence numbers (LSNs). Every durable change advances the WAL stream. Checkpoints periodically bound recovery work, and replication works by shipping WAL records to replicas.

The important lesson is not that this repo needs Postgres internals. The lesson is architectural:

- WAL is the source of truth for recovery
- checkpoints are bounded compaction points
- replication and auditing become possible because the commit stream is explicit

That same lesson applies to ACCESS logs and to any future proposal/apply workflow for governed writes.

## Git staging already behaves like a mini-WAL

Git is not usually described in WAL language, but the analogy is strong enough to guide design here.

- working tree: mutable pre-transaction state
- index: staged intended snapshot
- commit object plus ref update: published state

The load-bearing property is that `git add` gathers intended file content into a staging boundary before `git commit` publishes a new history node. A crash between those steps is recoverable because the intended state is still represented in Git's intermediate machinery.

This clarifies an important design point for the MCP write tools: the correct unit of atomicity is not a single file write. It is the staged set that will be committed together.

## Multi-file write tools should be designed as staged transactions

The current improvement plans already move in this direction, but WAL thinking sharpens the requirements.

For a multi-file semantic write:

1. validate every path and version token up front
2. compute the full staged state in memory
3. write or stage all mutated files without publishing a commit yet
4. publish once with a single commit
5. if any pre-publish step fails, roll back staged state rather than leaving a half-assembled transaction

That is the repository equivalent of WAL plus checkpoint. It is also the right model for:

- `memory_update_frontmatter_bulk`
- `memory_record_session`
- `memory_log_access_batch`
- aggregation runs that update summaries and archive processed entries together

## Rollback is the missing half of the current design gap

The active plan correctly identifies "stage multiple files and commit together" as the answer to partial-write risk. But WAL design adds a second requirement: if staging fails partway through, the tool needs an explicit rollback rule.

For Git-backed tooling, that usually means:

- do not publish a commit until the full staged set exists
- if a failure occurs before commit, remove temporary files and unstage any partial index changes
- surface the failure as an uncommitted transaction failure, not as a mysterious repo drift

Without that rollback rule, the system still behaves transactionally only in the happy path.

## A future SQLite index should stay derived, not canonical

WAL-friendly databases tempt a design leap: move the memory system into SQLite entirely. That would be the wrong lesson from this research.

The better lesson is:

- keep Markdown and JSONL as the canonical store
- use SQLite in WAL mode only for derived indexes, search accelerators, or health summaries
- rebuild derived state from canonical files and git history when needed

That preserves the repo's current strengths while borrowing mature WAL behavior where it actually helps.

## Relevance to agent-memory-seed

This topic directly changes how several active build plans should be read:

- batch write tools should be treated as staged transactions, not convenience wrappers
- aggregation should be framed as checkpointing an append-only log into materialized summaries
- rollback on staging failure is as important as the eventual single commit
- any future SQLite state should remain derived and rebuildable from the canonical repo

The architectural takeaway is that "single commit" is necessary but not sufficient. The right unit is a prevalidated staged transaction with an explicit rollback path and a single publication step.

## Sources

- SQLite documentation on WAL mode and checkpointing
- PostgreSQL documentation on WAL, checkpoints, and replication
- Git staging and commit model as discussed in existing repository plans and code
