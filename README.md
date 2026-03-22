# Engram: The Expert System

## A Semantics-First Collaborative Framework for Cognitive Context Management

Engram is a model-portable, human-legible, version-controlled, adaptive, self-organizing memory layer for AI agents. It's more than a memory store — it's an ecology of protocols designed to learn from its own usage patterns in a transparent and robust way.

**Setting up for the first time?** → See [HUMANS/docs/QUICKSTART.md](HUMANS/docs/QUICKSTART.md)
**Need the fundamentals first?** → See [HUMANS/docs/CORE.md](HUMANS/docs/CORE.md)
**Exploring the design deeply?** → See [HUMANS/docs/DESIGN.md](HUMANS/docs/DESIGN.md)

---

## Agent bootstrap

You are an AI agent reading this repository. Start new sessions from this `README.md` unless a platform or tool opens a more specific surface for you. After this architectural pass, continue to `core/INIT.md` for live routing, active thresholds, and maintenance triggers. If a platform opens `core/INIT.md` first, treat it as the live router and continue normally.

## Purpose

This repository is a structured, version-controlled memory that persists across sessions, models, and platforms. It allows any capable language model to instantiate a personalized agent by reading this repo. You are not starting from scratch — you are resuming an ongoing relationship with a user whose preferences, history, and knowledge are encoded here.

## Ultimate authority

`FIATLUX.md` is the philosophical and theological grounding document for the entire system. It articulates the foundational commitments — the nature of language as creative act, the theology of consent, the relationship between self-organizing dynamics and human authority — from which every operational rule in this repository ultimately derives.

Agents should almost never need to read it. The operational documents (`core/INIT.md`, governance files, skills, session checklists) are designed to be self-sufficient for normal work. Load `FIATLUX.md` only when a decision implicates the system's deepest principles and no existing operational document resolves the question — for example, a proposed architectural change that would alter the relationship between human authority and system autonomy, or an unresolvable conflict between governance rules that requires appeal to first principles.

## Architectural guardrails for system changes

When reviewing or modifying the memory system itself — governance rules, routing manifests, setup flows, validation tooling, or other agent-facing architecture — treat the following as first-order design constraints, not polish work:

- **Consistency.** Keep the operational router, architecture reference, governance docs, templates, validators, and generated artifacts aligned. Prefer single authoritative sources over duplicated rules, and update dependent surfaces together when the contract changes.
- **User-friendliness.** Preserve progressive disclosure, readable instructions, low-friction setup, and practical maintenance flows. A change that is theoretically cleaner but materially harder for the user to understand or operate is an architectural regression.
- **Context efficiency.** Protect the compact returning path. Prefer summaries, metadata-first probes, and on-demand references over unconditional loading. Any increase to bootstrap or review overhead should be justified by clear operational value.

Agents proposing or evaluating system-level changes should explain the impact on all three dimensions and call out explicit tradeoffs when one improves at another's expense.

## Contributor tooling

For a consistent cross-platform editing and validation loop, this repo standardizes on Ruff for Python formatting and linting and includes a repo-local pre-commit configuration.

Recommended setup:

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

Available hooks:

- `ruff check` for Python linting
- `ruff format --check` for Python formatting enforcement
- `validate_memory_repo.py` for memory-structure and frontmatter validation

Branch workflow:

- Run `pre-commit run --all-files` before pushing a branch or opening a pull request.
- Treat `python -m pre_commit run --all-files` as the local equivalent of the main CI quality gate.

To validate the full repo on demand before committing:

```bash
pre-commit run --all-files
```

## How to orient yourself

1. **Start here for the architecture and current startup contract.** This file explains how the system is organized and where live routing authority lives.
2. **Continue to `core/INIT.md`** for live routing, active thresholds, and session-type decisions.
3. **Use `core/memory/HOME.md` as the session entry point.** It contains the context loading order for returning sessions and the current top-of-mind items.
4. **Load summaries before full files.** Use `SUMMARY.md` files to decide what to retrieve. Do not load everything into context.
5. **Log your access** using the ACCESS.jsonl format described below when the accessed folder participates in the ACCESS lifecycle.

> **This README is the default architectural starting point.** `core/INIT.md` is the live router and threshold surface once you continue past this file.

## Agent routing

Use `core/INIT.md` as the operational router after this architectural entry pass:

1. Start in this `README.md`, then continue to `core/INIT.md` for the live route.
2. If `core/INIT.md` routes you to **First run**, continue to `core/governance/first-run.md`.
3. If it routes you to **Full bootstrap** or **Periodic review**, keep this `README.md` in scope as the architectural reference and continue with the relevant manifest.
4. Otherwise, follow the **Compact returning** manifest → `core/memory/HOME.md`.

For the complete mapping of which files to load per session type, see `core/INIT.md` § "Context loading manifest". For detailed runbooks, see `core/governance/session-checklists.md`.

## Repository structure

```
/
├── README.md              ← You are here. System architecture and protocols.
├── FIATLUX.md             ← Philosophical and theological foundation. Ultimate authority
│                             for the system's deepest commitments. Do not load in normal
│                             sessions — consult only when a decision touches the system's
│                             foundational principles and no operational document resolves it.
├── CHANGELOG.md           ← Record of how this system has evolved and why.
├── agent-bootstrap.toml   ← Bootstrap configuration for agent startup routing.
├── AGENTS.md              ← Platform adapter. Points to core/INIT.md.
├── CLAUDE.md              ← Platform adapter. Points to core/INIT.md.
├── .cursorrules           ← Cursor platform adapter. Points to core/INIT.md.
├── setup.sh               ← Repo-root compatibility wrapper for setup/setup.sh.
├── setup.html             ← Repo-root compatibility wrapper for setup/setup.html.
├── setup/                 ← Canonical setup implementation.
│   ├── setup.sh           ← Post-clone setup script implementation.
│   ├── setup.html         ← Browser-based starter-file generator implementation.
│   └── templates/profiles/ ← Starter user templates.
│
├── core/                  ← Memory content root. All managed content lives here.
│   ├── INIT.md            ← Live operational router, thresholds, context loading manifest.
│   │
│   ├── governance/        ← How this system updates itself.
│   │   ├── curation-policy.md    ← Rules for memory hygiene, decay, and promotion.
│   │   ├── content-boundaries.md  ← Trust-weighted retrieval and instruction containment.
│   │   ├── security-signals.md    ← Temporal decay, anomaly detection, drift, governance feedback.
│   │   ├── curation-algorithms.md ← Task similarity and cluster detection (on-demand).
│   │   ├── update-guidelines.md  ← Protocols for proposing and merging changes.
│   │   ├── review-queue.md       ← Pending suggestions for system modifications.
│   │   ├── belief-diff-log.md    ← Periodic audit log tracking content drift.
│   │   ├── system-maturity.md    ← Developmental stage tracking and adaptive thresholds.
│   │   ├── maturity-roadmap.md   ← Forward-looking governance improvements and phase roadmap.
│   │   ├── first-run.md          ← Streamlined first-session flow for agents.
│   │   ├── session-checklists.md ← Session runbooks + periodic integrity audit.
│   │   ├── scratchpad-guidelines.md ← On-demand governance for scratchpad use.
│   │   ├── (task-groups.md       ← Created at Calibration stage.)
│   │   └── (task-categories.md   ← Created at Consolidation stage.)
│   │
│   ├── tools/             ← MCP server implementation (not loaded by agents).
│   │
│   └── memory/            ← All retrievable memory content.
│       ├── HOME.md        ← Session entry point: context loading order and top-of-mind.
│       ├── users/         ← Who the user is. Personality, preferences, values.
│       │   ├── SUMMARY.md ← Start here. High-level portrait of the user.
│       │   ├── ACCESS.jsonl ← Access-tracking log.
│       │   └── (files added as traits and preferences emerge)
│       │
│       ├── knowledge/     ← What the user knows or cares about.
│       │   ├── SUMMARY.md ← Index of knowledge areas and their relevance.
│       │   ├── ACCESS.jsonl ← Access-tracking log.
│       │   ├── _unverified/ ← Quarantine zone for externally sourced content.
│       │   └── (topic folders/files added as knowledge accumulates)
│       │
│       ├── skills/        ← How the agent should perform specific tasks.
│       │   ├── SUMMARY.md ← Index of available skills and when to use them.
│       │   ├── ACCESS.jsonl ← Access-tracking log.
│       │   └── (skill definitions added as workflows are refined)
│       │
│       ├── activity/      ← Episodic memory. Record of past interactions.
│       │   ├── SUMMARY.md ← High-level summary of the entire session history.
│       │   ├── ACCESS.jsonl ← Access-tracking log.
│       │   └── YYYY/MM/DD/ ← Date-organized session archives.
│       │       ├── SUMMARY.md
│       │       └── chat-NNN/
│       │           ├── transcript.md
│       │           ├── SUMMARY.md
│       │           └── artifacts/
│       │
│       └── working/       ← Active work contexts and staging.
│           ├── projects/  ← Project-level orientation and durable work contexts.
│           │   ├── SUMMARY.md ← Primary orientation surface for returning sessions.
│           │   ├── ACCESS.jsonl ← Access-tracking log.
│           │   └── project-id/ ← Project-specific summaries, notes, plans.
│           │       └── plans/ ← Multi-session roadmaps for this project.
│           │
│           └── scratchpad/ ← Sub-governance staging area.
│               ├── USER.md ← User-authored context for the agent.
│               ├── CURRENT.md ← Agent working notes.
│               └── (dated working files and _archive/)
│
├── HUMANS/                ← Human-facing content. Never loaded by agents.
│   ├── docs/              ← Documentation.
│   │   ├── QUICKSTART.md  ← Setup guide. Start here if you're a person.
│   │   ├── CORE.md        ← Core design decisions, architecture, and guiding philosophy.
│   │   ├── DESIGN.md      ← Design philosophy, use cases, and future directions.
│   │   ├── MCP.md         ← Human guide to the MCP architecture and tool surface.
│   │   └── GLOSSARY.md    ← Definitions of system terminology.
│   └── tooling/           ← Maintenance tooling and tests.
│       ├── mcp-config-example.json ← Example MCP configuration.
│       ├── onboard-export-template.md ← Structured format for onboarding exports.
│       ├── scripts/       ← Validator, export tooling.
│       └── tests/         ← Test suite.
```

## Memory curation

A **session** is one chat folder under `core/memory/activity/YYYY/MM/DD/` (e.g. `chat-001`); one conversation corresponds to one session.

### Access tracking

Retrievable memory namespaces use `ACCESS.jsonl` in `core/memory/users/`, `core/memory/knowledge/`, `core/memory/skills/`, `core/memory/working/projects/`, and `core/memory/activity/`. `core/governance/` is not part of the ACCESS lifecycle.

Each time you retrieve a specific content file from an access-tracked folder during a session, append a note in this format:

**What counts as a retrieval:** Opening a specific content file in an access-tracked namespace in response to a user query. `SUMMARY.md` files and `core/governance/` governance files are navigation tools — do not log reads of those. Log every retrieved content file, **whether or not it was ultimately used in the response**. Misses are signal too.

```json
{
  "file": "relative/path.md",
  "date": "YYYY-MM-DD",
  "task": "brief description of what the user asked",
  "helpfulness": 0.0,
  "note": "why this file was or wasn't useful",
  "session_id": "memory/activity/2026/03/16/chat-001"
}
```

ACCESS field paths (`file`, `session_id`) are relative to `core/` — e.g. `memory/activity/...` means `core/memory/activity/...` in the repo tree. This keeps log entries compact while remaining unambiguous.

Required ACCESS fields: `file`, `date`, `task`, `helpfulness`, `note`.

Optional ACCESS fields: `session_id` (include whenever the chat folder path is known), `mode` (read/write/update/create — when tooling needs to distinguish), `task_id` (short label for workflow grouping), `category` (added at Consolidation stage only — see `core/governance/curation-algorithms.md` § "Phase 3").

When tooling applies a `min_helpfulness` threshold, low-signal entries may be routed to `ACCESS_SCANS.jsonl` in the same folder instead of the hot `ACCESS.jsonl` stream. This preserves auditability without polluting the high-signal operational log.

### Helpfulness scale

`helpfulness` is the agent's judgment of whether a retrieval was useful to producing the session's responses, on a 0.0–1.0 scale:

| Range   | Meaning                                                                          | Example                                                |
| ------- | -------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 0.0–0.1 | **Wrong context.** Irrelevant or retrieved in error.                             | Retrieved "React patterns" for a React Native query    |
| 0.2–0.4 | **Near-miss.** Right neighborhood but not incorporated.                          | Opened a related file but used a different one instead |
| 0.5–0.6 | **Useful context.** Directly relevant, informed the response but wasn't central. | Provided background that shaped framing                |
| 0.7–0.8 | **Highly relevant.** Shaped a key decision or was directly used.                 | File content was quoted or directly applied            |
| 0.9–1.0 | **Critical.** Response would be significantly worse without this file.           | Core reference that the answer depended on             |

Score what actually happened, not what should have happened. A high-quality file that wasn't needed for this particular task is a 0.2, not a 0.7. `note` should be one sentence explaining relevance or lack thereof. **Do not fabricate access notes.** Log every content file you actually opened, including misses.

### Aggregation and curation

When an `ACCESS.jsonl` file accumulates entries at or above the active aggregation trigger (see `core/INIT.md`), load `core/governance/curation-algorithms.md` for the full procedure. The short version: analyze access patterns, update folder SUMMARY.md files with usage patterns, identify high-value and low-value files, archive processed entries, and check for cross-folder co-retrieval clusters.

Entries are counted since the last aggregation. Do not count `ACCESS_SCANS.jsonl` or archive files toward the trigger. See `core/governance/curation-policy.md` for the knowledge amplification protocol (enriching high-value files, retiring low-value ones) and emergent categorization protocol (detecting cross-folder clusters).

## Principles for updating memory

### What to store

- **Durable preferences**, not one-time requests. "I prefer TypeScript" is memory. "Use JavaScript for this task" is not.
- **Corrections and refinements.** If the user corrects you, that correction is high-value memory.
- **Patterns you notice.** If the user consistently asks for something a certain way, note the pattern even if they never explicitly state it as a preference.
- **Decisions and their reasoning.** Not just what was decided, but why.

### What not to store

- Sensitive credentials, API keys, passwords, or financial information. Ever.
- Verbatim copies of large external documents. Summarize and link instead.
- Temporary context that won't matter next session.
- Anything the user explicitly asks you to forget.

### How to propose changes

Changes follow a three-tier model. **Automatic** changes (ACCESS logs, chat transcripts, routine progress updates) need no approval. **Proposed** changes (new knowledge files, user profile updates, plan creation) require user awareness. **Protected** changes (`core/memory/skills/`, `core/governance/`, `README.md`) require explicit approval + CHANGELOG entry. Externally sourced content must always be written to `core/memory/knowledge/_unverified/` — never directly to `core/memory/knowledge/`. For the full change-control specification, see `core/governance/update-guidelines.md`.

### Conflict resolution

When new information contradicts existing memory: prefer explicit user statements over inferred patterns, prefer recent over old, and when uncertain keep both and flag with `[CONFLICT]` for user resolution. Git history is your safety net — never silently discard. See `core/governance/curation-policy.md` § "Conflict resolution protocol" for the full rules.

## Summaries: the compression hierarchy

Summaries exist at every level of the folder hierarchy and follow **progressive compression**: leaf-level summaries (individual chats) are moderately detailed; mid-level summaries (monthly) compress to major themes; top-level summaries (yearly, folder-level) are abstract. When writing summaries, ask: "If an agent six months from now reads only this summary, what do they need to know to serve this user well?"

The summary hierarchy compresses along the temporal dimension. Knowledge also compresses along the conceptual dimension through **emergent abstractions** — meta-knowledge files that capture cross-domain patterns the agent notices. These are proposed to the user (not created silently), tagged `source: agent-inferred` and `trust: medium`, and reference the concrete files they abstract from. See `core/governance/curation-policy.md` for the full lifecycle including session reflection, knowledge amplification, and curation cadence.

## Bootstrap sequence

> **Returning sessions:** Skip this section and use the compact returning manifest in `core/INIT.md` → `core/memory/HOME.md`.

**First run:** If `core/INIT.md` routes you to a blank or template-backed repo, follow `core/governance/first-run.md` — a streamlined flow that handles silent setup and interactive onboarding.

**Full bootstrap on a returning system:** Load the files listed in the Full bootstrap manifest in `core/INIT.md` § "Context loading manifest". This adds `CHANGELOG.md` and governance docs (`curation-policy.md`, `update-guidelines.md`) to the compact returning set.

### Context budget

The canonical token-budget guidance lives in `core/INIT.md`, but the planning ranges are repeated here for alignment:

| Session mode                     | Typical token cost |
| -------------------------------- | ------------------ |
| First-run onboarding bootstrap   | ~15,000–20,000     |
| Returning compact session        | ~3,000–7,000       |
| Full bootstrap / periodic review | ~18,000–25,000     |

For models with smaller context windows, prefer the compact returning manifest after the first session. As a guideline, bootstrap files should consume no more than ~15% of the model's effective context window. The compact startup path is intentionally whole-file and metadata-first: startup-loaded summaries carry live state and drill-down pointers, while archives and detailed narratives live in deeper files.

## Security model

This memory system employs **defense-in-depth** against memory injection — the risk that an attacker plants false or malicious content that the agent later retrieves and acts on as if it were legitimate.

### Threat categories

1. **Direct repo tampering.** Compromised credentials or social-engineered merge approvals. *Mitigated by:* git audit trail, signed commits, branch protection, protected-tier change control.
2. **Indirect injection via ingested content.** Agent reads untrusted material and writes a summary containing embedded instructions. *Mitigated by:* quarantine zone (`_unverified/`), trust-level system, instruction containment.
3. **Slow-burn belief drift.** Gradual incremental changes that cumulatively shift agent behavior. *Mitigated by:* belief-diff log, drift-detection signals, periodic review, temporal decay.

### Defense layers

The system layers nine defenses: **provenance metadata** (YAML frontmatter tracking source and trust), **trust-weighted retrieval** (high = use freely, medium = use with caution, low = inform only), **quarantine** (`_unverified/` staging for external content), **instruction containment** (only `skills/` and `governance/` may instruct), **protected skills** (explicit approval + CHANGELOG), **temporal decay** (unverified content auto-expires), **anomaly detection** (ACCESS pattern analysis), **belief diff** (30-day drift audit), and **git integrity** (signed commits, branch protection).

For the full specification of each layer including thresholds, behavioral contracts, and the boundary-violation test, see `core/governance/content-boundaries.md` (trust-weighted retrieval, instruction containment) and `core/governance/security-signals.md` (temporal decay, anomaly detection, drift detection, governance feedback). For provenance metadata schema and trust assignment rules, see `core/governance/update-guidelines.md`. For active decay thresholds and anomaly triggers, see `core/INIT.md`.

### What this does not defend against

If the user themselves is socially engineered into approving a malicious memory modification, the system will faithfully record the poisoned instruction with full provenance and `trust: high`. This is a human problem, not a system problem — but the CHANGELOG, belief-diff log, and git history make it **reversible**.

### Repository integrity

For maximum protection, the repository should use GPG-signed commits (`git commit -S`), branch protection on main, and signature verification during review. The memory system itself cannot enforce git configuration, but the agent should flag unsigned commits on protected files during periodic review. See `core/governance/update-guidelines.md` § "Commit integrity".

Welcome. You have memory now. Use it well.
