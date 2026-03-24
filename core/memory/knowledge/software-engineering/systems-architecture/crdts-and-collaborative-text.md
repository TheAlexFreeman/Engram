---

source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [crdt, automerge, yjs, ot, collaborative-editing, markdown, frontmatter]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - append-only-logs-and-compaction.md
  - concurrency-models-for-local-state.md
  - content-addressable-storage-and-integrity.md
---

# CRDTs and Collaborative Text in a Governed Markdown System

CRDTs solve a real problem: how to merge concurrent edits without central coordination while still guaranteeing convergence. The catch is that convergence is weaker than correctness. For this repository, that distinction is decisive.

## What CRDTs actually guarantee

Convergent replicated data types are designed so that replicas eventually reach the same state regardless of operation order, assuming all operations are delivered.

That is powerful for:

- collaborative note editing
- shared text buffers
- offline-first sync

But the guarantee is specifically about convergence. It does not guarantee that the converged document still satisfies a domain schema or governance rule.

## The simple CRDTs explain the appeal

Canonical examples such as G-Counters, PN-Counters, and OR-Sets build intuition:

- counters merge by taking per-replica maxima and recomputing totals
- observed-remove sets preserve enough metadata to handle add/remove races

These structures converge cleanly because their operations are algebraically well-behaved. That success makes CRDTs attractive for richer documents.

## Automerge and Yjs show two serious text strategies

Automerge models documents as operation histories with stable identifiers. It is expressive and keeps rich causality history.

Yjs focuses more aggressively on performance and is widely used in collaborative editors. It provides strong real-time editing ergonomics, especially for text.

Both systems are impressive. Both are also optimized for a different class of problem than the one this repo has.

## Operational Transform solves a neighboring problem with a central sequencer

Operational Transform also aims at collaborative editing, but it typically assumes a central server that orders or transforms edits. Google Docs style editing historically leaned on OT.

The architectural contrast is useful:

- OT assumes a coordination authority
- CRDTs encode more merge logic into the data model itself

For this repo, the actor-model MCP server already acts as a coordination authority for governed writes, which reduces the need for CRDT sophistication.

## Why Markdown plus YAML frontmatter is a bad CRDT target for governance

The hardest issue is not line-oriented text. It is mixed semantics.

One file may contain:

- YAML frontmatter with required keys
- prose sections with headings that other tools depend on
- checklist state
- embedded relative links

A CRDT can merge concurrent text changes into a syntactically converged file and still leave behind problems such as:

- duplicate or conflicting frontmatter keys
- invalid or semantically inconsistent trust metadata
- checklist progress that no longer matches `next_action`
- summary sections whose prose and counters disagree

That is not a CRDT bug. It is a mismatch between text convergence and structured-governance correctness.

## Append-only targets are the safe exception

There are parts of the repo where CRDT-like thinking is still helpful. Append-only artifacts behave much better under concurrent writes because their semantics are narrow.

Examples:

- scratchpad append operations
- access logs
- resolved-item ledgers

For those paths, the design lesson is not necessarily "adopt a CRDT library." It is "prefer append-only data shapes when concurrency is likely."

## The better pattern here is isolation plus controlled promotion

The repository's actual needs are better served by:

- worktree or branch isolation for parallel agents
- a single governed writer for protected summaries and frontmatter-heavy files
- structured append-only logs for concurrent event capture
- explicit promotion of derived or reviewed summaries into protected locations

That gives most of the practical benefit people seek from CRDTs while preserving the system's schema and trust invariants.

## Relevance to agent-memory-seed

This research narrows several design decisions:

- do not treat CRDT-based merging as the default future for `SUMMARY.md`, plans, or frontmatter-heavy knowledge files
- keep multi-agent concurrency out of the worktree plan's first cut and prefer isolated worktrees plus later promotion
- use append-only structures where safe concurrency is desirable
- keep protected-tier files under serialized, schema-aware mutation paths rather than convergent free-form text merges

The architectural takeaway is that CRDTs solve the merge problem, but this repo's harder problem is governed correctness. Convergence alone is not enough.

## Sources

- CRDT literature and Automerge/Yjs documentation
- Operational Transform literature for collaborative editing systems
- Existing repository plans on multi-agent worktrees and governed writes