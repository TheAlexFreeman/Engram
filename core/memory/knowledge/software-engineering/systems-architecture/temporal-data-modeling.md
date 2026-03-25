---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [temporal, bitemporal, last-verified, freshness, event-sourcing, history]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - ../django/django-test-data-factories.md
  - ../../self/_archive/2026-03-19-tmp-data-loss-incident.md
  - concurrency-models-for-local-state.md
---

# Temporal Data Modeling for Trust and Freshness

Time in this repository is doing more than one job, but the current fields do not fully acknowledge that. `created`, `last_verified`, ACCESS dates, and git commit history all record different temporal facts. A cleaner temporal model would reduce ambiguity in trust decay and freshness tooling.

## Transaction time and valid time are different axes

Bi-temporal modeling distinguishes:

- transaction time: when the system recorded a fact
- valid time: when the fact was considered true of the world or confirmed

That distinction maps well onto current fields:

- `created` is transaction time for the first write
- `last_verified` is closer to valid time for "this content was reviewed and considered good as of this point"

The problem is that the current docs often talk about these values as if they were interchangeable freshness signals. They are related, but not identical.

## Event logs already provide one temporal layer

Git history and ACCESS logs are already event streams. That means the repository implicitly supports questions like:

- when was this file first introduced
- when was it last changed
- when was it last consulted

What it does not yet support cleanly is the verification timeline. Overwriting `last_verified` gives only the newest fact, not the verification history.

## Slowly changing dimensions clarify the trade-off

Data warehouse terminology is useful here:

- Type 1: overwrite the old value
- Type 2: store a new row or record for each historical state

`last_verified` is currently a Type 1 field. That keeps files simple but discards the history of prior reviews. For many cases that is acceptable. The important design point is to recognize the trade-off explicitly.

If the system later needs stronger auditability, the better answer is probably not to make every file's frontmatter more complex. It is to record verification events in an append-only auxiliary log.

## Freshness is not just elapsed time

Fixed thresholds are easy to explain, but actual freshness depends on at least three things:

- age since creation or verification
- change intensity in the related source material
- importance of the artifact

This matters most for worktree mode. A codebase knowledge note that was verified 20 days ago but whose source files changed 40 times may be more stale than a note verified 90 days ago against an untouched module.

That does not mean fixed thresholds are wrong. It means they are fallback heuristics when richer source-change data is absent.

## Event timestamps deserve more precision than dates alone

ACCESS logs currently emphasize dates. For some uses that is enough, but finer event sequencing becomes valuable when asking:

- what was orientation reading versus final verification
- did the agent read before writing
- how much batching happened inside one session

That argues for eventually capturing an event timestamp or sequence number in access and verification logs even if human-facing summaries still compress to dates.

## Relevance to agent-memory-seed

This research changes how several active plans should be framed:

- freshness tooling should treat `created`, `last_verified`, and host-repo change history as different signals, not interchangeable timestamps
- ACCESS logging should eventually carry a more precise event time or sequence than date-only records
- if verification history becomes important, it should be stored as append-only review events rather than by endlessly growing frontmatter
- trust decay should remain threshold-based for now, but the design should leave room for richer source-change-aware freshness scoring

The architectural takeaway is that the repository already has temporal data. It just needs to stop flattening distinct temporal meanings into one generic notion of "last updated".

## Sources

- Temporal database literature on valid time and transaction time
- Data warehousing literature on slowly changing dimensions
- Existing repository rules around `created`, `last_verified`, and ACCESS logs
