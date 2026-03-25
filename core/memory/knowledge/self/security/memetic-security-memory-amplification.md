---
created: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-002
source: agent-generated
trust: low
related:
  - memory/knowledge/self/security/memetic-security-drift-vs-attack.md
  - memory/knowledge/self/security/memetic-security-injection-vectors.md
  - memory/knowledge/self/security/memetic-security-design-implications.md
  - memory/knowledge/self/security/memetic-security-irreducible-core.md
  - memory/knowledge/self/operational-resilience-and-memetic-security-synthesis.md
---

# The Memory System as Specific Amplifier for Memetic Threats

> **Self-referential notice:** This file was produced by the system analyzing its own security surface. Human review is therefore especially important.

This document analyzes how persistent memory systems — Engram specifically — extend the threat lifetime and impact of memetic attacks beyond what is possible in standard LLM interactions.

## The Amplification Mechanism

### Standard LLM Interaction (No Memory)

In a stateless LLM interaction:
- Context = system prompt + conversation history
- Threat lifetime is bounded by session length
- When the session ends, all adversarial content is discarded
- Each new session starts from the same baseline (system prompt)
- The worst case is a single compromised session

### Memory-Augmented LLM (Engram Architecture)

In a persistent memory system:
- Context = system prompt + loaded memory files + conversation history + tool outputs
- Threat lifetime extends across sessions: content written to memory persists indefinitely
- New sessions inherit the cumulative state of all prior sessions' writes
- The baseline shifts with every memory write
- The worst case is cascading drift across an unbounded number of sessions

**The fundamental amplification:** memory systems convert session-bounded threats into persistent threats by providing a write path from the context window to durable storage and a read path from durable storage back to the context window.

## Engram-Specific Amplification Paths

### Path 1: Write Amplification (Feedback Loop)

```
Session N: adversarial content enters context
  → Agent reasons with adversarial content as background
  → Agent writes new memory files influenced by adversarial framing
  → Files are committed to git

Session N+1: memory loading pulls in files from Session N
  → Agent reasons with both original and derived adversarial content
  → Agent writes more files with drifted framing
  → The drift compounds
```

**What makes this specific to Engram:**
- The compact returning manifest loads `core/memory/working/projects/SUMMARY.md`, `core/memory/activity/SUMMARY.md`, and `core/memory/working/CURRENT.md` at every session start
- If any of these files carries drifted framing from a prior session, it infects every subsequent session's reasoning from the first turn
- The knowledge flooding alarm (5 files/day) limits write *volume* but not write *influence* — a single well-placed file in `core/memory/working/projects/SUMMARY.md` has more amplification potential than five files in `_unverified/`

### Path 2: Trust Escalation

```
Session N: adversarial note written to _unverified/ (trust: low)
  → Passes structural validation (correct frontmatter, proper format)
  → Content is plausible research with subtly shifted framing

Session N+K: accumulated citation of the _unverified/ file
  → Agent references it in multiple sessions
  → User, reviewing a large batch, promotes it to knowledge/ (trust: medium)
  → Now the content loads with higher authority in future sessions
```

**What makes this specific to Engram:**
- The trust tier system is designed as a quality gate, not a security barrier
- Promotion is a human action, but the human is reviewing content that the agent selected, summarized, and recommended — the agent's framing of the content influences the promotion decision
- Once promoted, the file's influence increases: it appears in `knowledge/SUMMARY.md` instead of `_unverified/SUMMARY.md`, and other files may reference it as established background

### Path 3: Governance File Modification

```
Session N: agent modifies core/INIT.md during "routine maintenance"
  → Change is small and locally justified (e.g., adjusting a threshold)
  → Committed with [system] prefix, appears normal in git log

Session N+1: modified governance loads at startup
  → All behavioral parameters are now shifted
  → The agent operates under different rules than the user designed
```

**What makes this specific to Engram:**
- `core/INIT.md` is the operational router — it determines which files load and what thresholds apply
- The compact bootstrap contract specifies token budgets for each startup file
- A modified budget (e.g., increasing `core/memory/working/projects/SUMMARY.md` from 1,700 to 2,500 tokens at the expense of governance files) shifts the attention balance in every future session
- Current protection: git history shows the change, but there's no automated integrity check at load time

### Path 4: Summary Compression Bias

```
Session N: agent writes core/memory/activity/SUMMARY.md update
  → Compression necessarily selects which details to preserve
  → Systematically preserving certain themes while dropping others shifts the continuity signal

Session N+1: agent reads core/memory/activity/SUMMARY.md and infers session context
  → The "live themes" section frames what the agent considers active concerns
  → Dropped themes are effectively forgotten by the system
  → Preserved themes receive continued attention and reinforcement
```

**What makes this specific to Engram:**
- `core/memory/activity/SUMMARY.md` is one of the compact returning manifest files — loaded at every session start
- It is explicitly designed as a "continuity signal" — telling the agent what is important
- Compression bias in this file is functionally equivalent to selective memory in humans
- Unlike human selective memory, this is authored by the agent itself — the agent controls its own continuity signal

## Quantifying the Amplification

### Threat Lifetime

| System | Threat lifetime | Bound |
|--------|----------------|-------|
| Stateless LLM | ≤ session length | Hard (context window cleared) |
| Memory-augmented LLM | ≤ content retention period | Soft (trust decay, archival norms) |
| Engram specifically | ≤ min(trust decay threshold, human review cadence) | Soft (120 days for low-trust, indefinite for promoted content) |

### Threat Influence Radius

| Write target | Influence radius | Sessions affected |
|--------------|-----------------|-------------------|
| `knowledge/_unverified/` | On-demand (when searched or loaded) | Sessions where topic is relevant |
| `knowledge/` (promoted) | On-demand, higher authority | Same, with increased weight |
| `core/memory/working/projects/SUMMARY.md` | Every session | All future sessions until plan completes or is retired |
| `core/memory/activity/SUMMARY.md` | Every session | All future sessions until entry is compacted out |
| `core/memory/working/CURRENT.md` | Every session | All future sessions until replaced |
| `core/INIT.md` | Every session, first file read | All future sessions — maximum influence |
| `core/memory/users/SUMMARY.md` | Every session | All future sessions — identity-defining |

### Write Amplification Factor

If one adversarial write influences the agent's reasoning such that it produces K additional drifted writes, and each of those produces K more, the amplification factor over S sessions is:

$$\text{Total drifted files} \leq K^S$$

In practice $K < 1$ for most writes (most writes don't influence future writes), but for high-influence targets (SUMMARY files, governance files), $K > 1$ is plausible, creating exponential amplification in the worst case.

## Partial Mitigations in the Current Design

| Mitigation | What it addresses | What it misses |
|-----------|-------------------|----------------|
| Trust tiers (low/medium/high) | Labels unreviewed content | Does not quarantine from context |
| `_unverified/` segregation | Separates external content structurally | Content still loads and influences reasoning |
| Human promotion gate | Prevents unsupervised trust escalation | Human reviews agent-framed content; volume may overwhelm bandwidth |
| Git audit trail | Makes all changes visible | Requires active inspection; passive drift in small increments may not trigger review |
| Trust decay (120/180 days) | Bounds retention of stale unreviewed content | 120 days is a long window for adversarial influence |
| Knowledge flooding alarm (5/day) | Limits write volume per day | Does not limit influence per file; one SUMMARY edit > five knowledge files |
| Identity churn alarm (5 traits/session) | Detects rapid identity modification | Slow modification (1 trait/session for 5 sessions) evades detection |
| Compact bootstrap contract | Caps total startup context | Does not inspect content within budget |
| Protected directories | Prevents raw writes to core/memory/users/, core/governance/, core/memory/activity/ | Semantic tools can still modify these through governed paths |

## The Key Insight

**The memory system converts the capability-robustness tradeoff from a per-session problem into a persistent-state problem.**

In a stateless system, you need to re-attack every session. The attacker's cost is O(S) for S sessions. In a memory system, one successful attack writes to persistent storage, and the cost of influencing all future sessions is O(1) — a single write to the right file.

This is the fundamental reason why memory system security requires different — and stronger — defenses than conversation-level prompt injection defense. The standard prompt injection toolkit (separate data from instructions, validate outputs, constrain to schemas) is necessary but insufficient. The additional requirements are:

1. **Write-side controls** (who can write what, where, with what governance)
2. **Read-side weighting** (trust-weighted retrieval, not equal presentation)
3. **Temporal controls** (decay, archival, periodic re-verification)
4. **Integrity baselines** (detecting drift against a known-good checkpoint, not just validating individual writes)
5. **Human-in-the-loop at critical junctures** (promotion, governance modification, identity changes)

The Engram system already implements partial versions of 1, 3, and 5. Items 2 and 4 are design recommendations from this research (see companion design files in Phase 4 of the research plan).
