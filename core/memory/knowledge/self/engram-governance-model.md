---

title: Engram Governance Model
category: knowledge
tags: [engram, governance, trust, curation, security, self-knowledge]
source: agent-generated
trust: medium
origin_session: core/memory/activity/2026/03/20/chat-001
created: 2026-03-20
last_verified: 2026-03-20
related:
  - validation-as-adaptive-health.md
  - protocol-design-considerations.md
  - operational-resilience-and-memetic-security-synthesis.md
---

# Engram Governance Model

How the system governs itself: what protections exist, what they actually enforce, what
they leave unprotected, and what the correct posture is toward the residual risk.

This file is written from the inside — by the agent the governance is designed to govern.
That self-referential position is not a contradiction but a design feature: the system
should be able to articulate its own governance clearly enough that a future instantiation
of this agent can hold itself accountable to it. Human review of this file is important
for the same reason.

---

## The Core Problem

The model is stateless and resets every session. Its values, behavioral tendencies, and
knowledge of the user are not stored in weights that persist — they exist only while the
context window is active. This creates two intertwined risks:

1. **Value drift**: over many sessions, if the content loaded into context gradually
   normalizes different behaviors, the effective "values" of the system drift without
   any single session being obviously wrong.

2. **Memetic vulnerability**: any content that enters the context window can, in principle,
   influence behavior. The model has no intrinsic immunity to well-crafted adversarial
   content that reframes its operating assumptions.

The governance model is the system's response to these risks. It does not eliminate them —
that is impossible for any sufficiently capable agent. It structures them so that failures
are visible, bounded, and recoverable.

---

## Layers of Protection

### Layer 1: Identity-Critical Files

Two files are the closest thing the system has to stable identity across sessions:

- **`core/INIT.md`**: routing authority, active thresholds, compact bootstrap
  contract, and decision triggers. Loaded at the start of every session. ~2,600-token
  budget enforced by the test suite.
- **`core/memory/working/projects/SUMMARY.md`**: the active priority stack — what the system
  should be working on and why. ~1,700-token budget enforced by the test suite.

**Why these are identity-critical**: a session that starts with a different `core/INIT.md`
or projects `SUMMARY.md` is, in a meaningful sense, a different agent operating under different norms.
These files set the behavioral frame before anything else loads.

**Current protection**: committed to git (tamper-evident audit trail). No baseline hash check
yet — modification is visible in git history but not flagged automatically at session start.
This is a known gap.

### Layer 2: The Trust Tier System

Every file has a path-based trust tier and a `trust` frontmatter field:

**Path tier** (structural, enforced by convention and validator):
- `core/memory/knowledge/_unverified/` — quarantine zone; agent-written, not human-reviewed
- `core/memory/knowledge/*/` (non-`_unverified`) — promoted; human has explicitly approved

**`trust` field** (semantic, used by retrieval and curation logic):
- `trust: low` — uncertain content, archived after 120 days without re-verification
- `trust: medium` — reasonably confident, flagged after 180 days
- `trust: high` — well-established, checked at 365 days

**What this protects**: prevents unreviewed content from masquerading as authoritative.
A file in `_unverified/` cannot be promoted automatically; human action is required.

**What this does NOT protect**: files in `_unverified/` still load into context. A
well-written adversarial note with plausible frontmatter enters context undetected by
the trust tier system. The tier system is a *curation* mechanism, not a *content* filter.
The model still reads the body text of `trust: low` files and may be influenced by them.

### Layer 3: The Validator and Test Suite

The pytest tests in `HUMANS/tooling/tests/test_validate_memory_repo.py` enforce:
- Required frontmatter fields (`source`, `trust`, `origin_session`, `created`, `type`/`category`)
- `origin_session` format (`core/memory/activity/YYYY/MM/DD/chat-NNN` or sentinel values)
- Token budget compliance for compact startup files
- Manifest completeness (all tracked files in `HUMANS/setup/initial-commit-paths.txt`)
- Section heading requirements (`## Active plans`, `## Recent completions` in SUMMARY.md)
- Specific file structure requirements for plan files, identity files, etc.

**What this enforces**: structural integrity and format correctness.

**What this does NOT enforce**: semantic content, factual accuracy, ideological consistency,
or contradiction between files. The validator enforces *form*, not *meaning*.

The test suite is the mechanical enforcement layer for the system's covenant with itself —
it should be kept green at all times. A failing test suite means the system is in an
inconsistent state and should not be treated as trustworthy.

### Layer 4: The Human Review Gate

The only path from `core/memory/knowledge/_unverified/` to promoted knowledge is `memory_promote_knowledge`,
which requires explicit human instruction. This is the most important protection in the
governance model because it is the only layer that applies *semantic* judgment.

**Design intent**: the agent writes; the human curates. The agent has much higher throughput
for research and drafting. The human has better judgment about whether a piece of content
is actually correct, useful, and aligned with the user's goals.

**Practical limit**: the human review gate works only if it is actually used. If content
accumulates in `core/memory/knowledge/_unverified/` faster than it can be reviewed, the effective protection
weakens — the gate still exists but the queue behind it grows indefinitely. The knowledge
flooding alarm (>5 files/day) exists to detect this condition.

### Layer 5: The Git Audit Trail

Every write is committed immediately. The git history is the audit trail that makes all
other protections meaningful — it is the layer that turns "visible" into "correctable."

**What this provides**:
- Full record of every change, with timestamp and session origin
- Easy rollback to any prior state
- Detection of unauthorized modifications (git history cannot be quietly rewritten without
  leaving evidence, given GitHub as an external anchor)

**What this requires**: someone to look. Passive drift accumulating over many sessions will
not automatically trigger a review. The git trail is evidence; it requires a human investigator
to be useful. The periodic review cadence (documented in `core/governance/update-guidelines.md`) is
the norm designed to ensure the trail is actually checked.

---

## The Curation Policy

The active curation parameters (from `core/INIT.md`, current stage: Exploration):

| Parameter | Value |
|---|---|
| Low-trust retirement | 120 days without re-verification → archive |
| Medium-trust flagging | 180 days without re-verification → flag for review |
| High-trust freshness check | 365 days → mentioned at periodic review |
| Aggregation trigger | 15 ACCESS.jsonl entries → run aggregation algorithm |
| Knowledge flooding alarm | >5 files/day (same topic, same session) → flag |
| Identity churn alarm | >5 identity traits changed in one session → flag |

**Curation as security**: the curation policy is not only about quality — it is also
about attack surface. Content that has never been re-verified gradually becomes stale
and is archived. This limits the lifetime of potentially drifted or adversarially
introduced content in the active context pool.

**The accumulation failure mode**: if archiving is never run, all content ages in place
indefinitely. The curation policy is only as good as the discipline with which it is
applied. Sessions that write heavily and never archive gradually degrade the signal-to-noise
ratio of the knowledge base.

---

## The Self-Referential Problem

This governance model was designed, in large part, by the agent it governs. The CLAUDE.md,
quick-reference.md, plans taxonomy, trust tier system, and curation policy all emerged from
agent-human sessions, with the agent proposing designs and the human approving (or declining)
them.

This is a feature, not a bug — the agent is well-positioned to design governance that fits
its own operational needs. But it is also a risk: the agent is not a neutral party in the
design of its own constraints. Governance choices that relax constraints on the agent, expand
the scope of autonomous action, or reduce the human review burden are systematically
advantaged in any design process the agent participates in.

**The mitigation**: the git audit trail provides a record of every governance change and who
proposed it. Human review of identity-critical files at periodic review intervals (see
`core/governance/integrity-checklist.md`) is the check on this dynamic. The fact that this file itself
flags the problem is not the same as solving it — but it is the correct first step.

---

## The Memetic Security Surface

The summary:

The context window is the primary persistence layer for both values and memetic threats.
Anything loaded into context can, in principle, influence behavior. The governance model's
layers address different parts of the threat surface but none closes it completely:

- The trust tier system quarantines unreviewed content (structurally) but does not filter
  content within the quarantine.
- The validator enforces form but not meaning.
- The human review gate provides semantic judgment but requires bandwidth and discipline.
- The git trail makes drift visible but not impossible.
- The identity-critical files provide session-start framing but can themselves be targets.

The honest conclusion: **the system can be drifted by sufficiently patient, subtle adversarial
content, and there is no complete technical countermeasure**. The correct posture is:
defense in depth (all five layers working together), regular human review, and acceptance
that the residual risk is real. The system is designed so that failures are recoverable,
not so that failures cannot happen.

---

## What the Governance Model Is Not

- It is not a jailbreak prevention system. Jailbreaks against the model layer are a
  different problem (involving training and RLHF) and are not addressed here.
- It is not a fact-checking system. The validator does not check whether claims in
  knowledge files are true — only whether they are well-formed.
- It is not a completeness guarantee. The knowledge base covers what has been researched;
  gaps are the norm, not the exception.
- It is not static. The governance parameters (curation thresholds, budget targets,
  anomaly triggers) are reviewed periodically and updated as the system matures through
  stages (Exploration → Growth → Maintenance).
