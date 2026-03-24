---

title: Validation as Adaptive Health — How the Test Suite Closes the Loop
category: knowledge
tags: [self-knowledge, validation, governance, curation, adaptive-systems, health]
source: agent-generated
trust: medium
origin_session: core/memory/activity/2026/03/20/chat-002
created: 2026-03-20
last_verified: 2026-03-20
related:
  - engram-governance-model.md
  - operational-resilience-and-memetic-security-synthesis.md
---

# Validation as Adaptive Health — How the Test Suite Closes the Loop

The Engram validation layer is not merely a correctness guard. It is the mechanism through
which the memory system develops and maintains health *in proportion to how it is actually
used*. This note unpacks that claim and identifies where the model could be sharpened.

This is agent self-knowledge — a description of the system's own design from the inside,
intended for future sessions. Human review of the accuracy of the claims is appropriate.

---

## The Health Problem for a Living Memory System

A static knowledge base degrades silently. Files accumulate without being read. Curation
disciplines slip incrementally — one missing `last_verified` field, then ten, then the
field means nothing. Identity-critical startup files bloat until the context-budget
assumptions they were written against no longer hold. None of these failures are
catastrophic in a single session; all of them compound across sessions into a system
that is formally intact but functionally unreliable.

The validation layer's job is to make these failure modes *visible on a session-by-session
basis*, before they compound. What makes it interesting is that several of its checks are
not abstract correctness assertions — they detect drift relative to how the system is
actually being used.

---

## Four Ways Validation Is Usage-Adaptive

### 1. ACCESS.jsonl coverage checks surface dormant files

The validator checks whether files in `core/governance/`, `core/memory/skills/`, `core/memory/users/`, and `core/memory/activity/` have
been accessed within a configurable window (default 30 days; overridable via
`MEMORY_VALIDATE_COVERAGE_WINDOW_DAYS`). A warning fires when a file has not appeared in
any ACCESS.jsonl entry within that window.

This is directly usage-adaptive: a file that the system has never needed in a month is a
candidate for archiving regardless of its content quality. The check doesn't know *why*
the file hasn't been accessed — it might be genuinely useless, or it might be a conceptually
important file the agent has been routing around. But it creates a signal that human review
can act on, and the signal is grounded in actual session behavior rather than an abstract
quality assessment.

### 2. Token budget tests for identity-critical files enforce context-window fitness

`core/INIT.md` and `core/memory/working/projects/SUMMARY.md` are loaded at the start of every returning
session. The test suite enforces approximate token-count ceilings for both files. When either
file exceeds its ceiling, the test fails.

This health check is adaptive in the sense that the ceiling is set by the system's actual
bootstrap constraint: the returning startup path has a ~7,000-token budget, and the identity-
critical files must fit within it. If the system's usage patterns shift — if sessions become
longer, if the startup path gains or loses steps — the appropriate ceiling values change. A
ceiling that was correct last month may be wrong next month. The test makes the mismatch
visible immediately rather than letting it accumulate silently.

### 3. Frontmatter validation enforces curation discipline proportionally to volume

The validator checks every content file in `core/memory/users/`, `core/memory/knowledge/`,
`core/memory/skills/`, and `core/memory/working/projects/` for required frontmatter fields (`source`, `origin_session`, `created`, `trust`),
valid field values, and correct `origin_session` format. It also enforces contract-specific
rules: knowledge files may set `last_verified`, `_unverified/` files must not.

This check is adaptive not in its logic but in what it *surfaces*. A session that writes
five new knowledge files and forgets `trust: medium` on two of them generates two new errors.
A session that writes forty files and forgets `trust` on twenty generates twenty errors. The
error count tracks the *volume* of curation slippage, and that volume is itself a function
of how heavily the session was used for knowledge production. The check doesn't punish slow
sessions or forgive busy ones — it holds the standard constant and lets the error count
reflect actual behavior.

### 4. Compact-path structure validation catches startup-path drift

The validator checks that `core/memory/working/projects/SUMMARY.md`, `core/memory/activity/SUMMARY.md`, and `core/INIT.md`
have structurally appropriate content: not just correct frontmatter but the right *shape* of
information — active items, retrieval guidance, live thresholds. When these files accumulate
narrative prose rather than compact state, warnings fire.

This is adaptive because what counts as "compact" is relative to the startup budget. The
check enforces the *principle* — startup-path files answer live-state questions, not
archival questions — which remains valid whatever the current budget is. As the system's
startup path evolves, the check remains relevant without requiring modification.

---

## What Validation Does Not Do (But Could)

The current validation layer is reactive: it reports problems that have already occurred.
Several directions would make it more proactive and more tightly coupled to actual usage:

### Usage-weighted staleness decay

The current staleness model is binary: a file either has been accessed within the window
or it hasn't. A richer model would compute a staleness score proportional to the *gap*
between a file's actual access frequency and its expected frequency given its role. A
governance file that is supposed to be checked monthly and hasn't been touched in 60 days
has a different health implication than a reference file that has been heavy-loaded for
six months and then gone quiet. The ACCESS.jsonl log contains the raw material for this
computation; the validator doesn't exploit it.

### Cluster-aware redundancy detection

The aggregation pipeline (Phase 1→2→3 in `core/governance/curation-algorithms.md`) identifies files
that are co-retrieved across sessions, which implies topical relatedness. The validator
could use this structure to flag clusters of closely related files that have not been
consolidated — a sign that knowledge is being added at a faster rate than it is being
synthesized. This would make the health check sensitive to the *shape* of knowledge
accumulation, not just its volume.

### Differential validation between sessions

Currently the validator produces a static report (N errors, M warnings). It does not
compare this report to the previous session's report. A differential mode — "this session
introduced 3 new errors and cleared 5 old warnings, net improvement" — would give a
causal picture of each session's effect on health, which is more actionable than an
absolute score and better suited to a system where health is expected to be a moving target.

### Budget tiering by mode

The token-budget checks currently enforce a single ceiling for each file. But the bootstrap
TOML defines multiple modes (`returning`, `full_bootstrap`, `periodic_review`, `automation`)
with different total budgets. The validator could enforce per-mode per-file ceilings rather
than a single aggregate, making it possible to catch cases where a file is fine for the
`returning` startup path but would push the `full_bootstrap` path over budget.

### Calibration-stage task-group validation

The ACCESS.jsonl `task` field is free-text. As the system matures toward Phase 2
(task-string normalization), free-text variance in the `task` field will create
normalization noise. A validator check that warns when many `task` strings appear
semantically unique (no near-neighbors within the same session window) would flag sessions
where the user or agent is not anchoring task descriptions consistently — catching a
calibration problem before it distorts the aggregation output.

---

## The Deeper Pattern

The validation layer embodies a design principle worth naming explicitly: *health is not a
property of files in isolation, it is a property of the system's relationship to its usage*.

A file with perfect frontmatter that is never read is less healthy, in the sense that
matters, than a file with a missing `last_verified` field that is retrieved in every session.
The validation layer increasingly approximates this truth — the ACCESS coverage check is
the clearest instance — but the approximation is incomplete. The gap between the health
the validator measures and the health that actually matters is the territory where future
improvements live.

The developmental governance frame (articulated in `session-2026-03-20-cowork-review.md`)
points in the same direction: health checks should become more sophisticated as the system's
usage history grows. Early sessions need basic correctness enforcement. Later sessions, with
real ACCESS logs and real task patterns, can support causal, usage-grounded health metrics.
The validator's design should be treated as a living artifact that matures alongside the
system it monitors.
