# Scratchpad Guidelines

> **Load:** On-demand — when you need to write to `core/memory/working/USER.md`, `core/memory/working/CURRENT.md`, or `core/memory/working/notes/`, or when reviewing scratchpad lifecycle during session end. The compact read/write steps for normal sessions are in `core/governance/session-checklists.md`. You do not need to load this file just to read `core/memory/working/USER.md` or `core/memory/working/CURRENT.md`.

The `core/memory/working/notes/` folder is a staging area that sits between ephemeral session context (which disappears) and formal memory (which requires governance overhead). It operates below the governance layer: no frontmatter, no approval requirements, no CHANGELOG entries. Content here is either promoted to formal memory when it earns it, or cleared when it doesn't.

---

## The two scratchpad files

### USER.md

`core/memory/working/USER.md` belongs to the user. It is their channel to the agent — a place to inject current priorities, temporary constraints, and session context without going through the formal memory system.

- **Trust:** `high`. Treat its contents as direct user instruction.
- **Author:** User only. Do not modify this file unless explicitly asked to.
- **Read:** Every session start, after loading identity and knowledge summaries. Skip if it contains only the default placeholder.
- **Acknowledging content:** If USER.md has substantive content, weave the most relevant parts into your greeting naturally — don't announce it as a status readout. "I see you mentioned..." is fine; itemising the file's contents is not.
- **Stale entries:** You may gently surface entries that look outdated ("Your notes still mention the March deadline — want me to clear that?") but never clear them unilaterally.

### CURRENT.md

`core/memory/working/CURRENT.md` is the agent's working notes file — a place to track provisional observations, draft abstractions, and cross-session hypotheses that aren't yet ready for formal memory.

- **Trust:** `medium`. Treat its contents as agent-inferred and provisional until confirmed.
- **Author:** Agent only.
- **Read:** Every session start, after USER.md. Skip if it contains only the default placeholder.
- **Write protocol:** See § "Writing to CURRENT.md" below.

**Do not log reads of either scratchpad file to ACCESS.jsonl.** Scratchpad is a communication channel, not part of the retrievable memory system. ACCESS tracks retrieval quality; scratchpad reads are always-on overhead.

---

## What belongs where

| Content type | Destination |
|---|---|
| Confirmed user preference or trait | `core/memory/users/` — propose via normal governance |
| Verified factual knowledge | `core/memory/knowledge/` — propose via normal governance |
| Confirmed skill or repeatable workflow | `core/memory/skills/` — propose, protected-tier |
| Multi-session roadmap or investigation plan | project plans under `core/memory/working/projects/` — progress updates automatic; create/archive/scope changes proposed |
| Governance or process change | `core/governance/review-queue.md` |
| Temporary user context (hours to days) | `core/memory/working/USER.md` |
| Unconfirmed observation worth tracking across sessions | `core/memory/working/CURRENT.md` |
| Draft abstraction awaiting more evidence | `core/memory/working/CURRENT.md` or a dated file in `core/memory/working/notes/` |
| One-session context with no follow-up needed | Nowhere — let it go |

**Deciding between scratchpad and formal memory:** Ask "Would this still matter in three sessions?" If yes, it belongs in formal memory (propose it). If unsure, scratchpad. If no, don't write it anywhere. Scratchpad is a staging area for things with genuine cross-session value that haven't yet met the evidence bar for formal memory — not a dumping ground for uncertainty.

---

## Writing to CURRENT.md

- **Date the entry** and link the session: `<!-- YYYY-MM-DD, session: core/memory/activity/YYYY/MM/DD/chat-NNN -->`
- **State confidence explicitly** at the start of each entry: "Observation (unconfirmed):", "Hypothesis:", "Pattern (needs more data):", "Draft abstraction:". This prevents a future agent from treating a provisional note as established fact.
- **Keep entries short** — one to three sentences pointing at the observation, not a full argument. If an observation requires extensive reasoning to make sense, it probably needs to be a formal proposal or a dated working file.
- **One observation per entry.** Don't bundle multiple unrelated observations into one block.

For longer working content — draft knowledge files, partial skill definitions, extended hypotheses — create a separate dated file: `core/memory/working/notes/YYYY-MM-DD-brief-topic.md`. Reference it from CURRENT.md so it's discoverable. CURRENT.md is the index; dated files hold the detail.

---

## Promotion path

During session end, review CURRENT.md before writing your reflection:

1. **Ready to promote?** Has an observation been confirmed across 3+ sessions, or did the user explicitly validate it this session? Propose it to the appropriate folder using the normal governance process. Remove the entry from CURRENT.md after the proposal is accepted — not before.

2. **Still developing?** Leave it. Update the session link to the current session so freshness is visible. An entry whose session link is the current session was actively considered; an old session link means it's aging toward cleanup.

3. **Stale or disproved?** Clear it. No CHANGELOG entry needed unless the content materially influenced session behavior across multiple sessions.

**Three-session rule:** Any entry whose session link has not been updated for three or more sessions should be cleared during the next session-end review. Three sessions without renewal means the observation wasn't strong enough to act on. Promote it or drop it.

Dated working files (`core/memory/working/notes/YYYY-MM-DD-topic.md`) follow the same logic. During aggregation, check whether any dated files older than the active low-trust retirement threshold are no longer referenced from CURRENT.md — if so, move them to `core/memory/working/notes/_archive/`.

---

## What not to write in scratchpad

- **Credentials, tokens, or sensitive information** — never, anywhere in the repo.
- **Formal decisions requiring a CHANGELOG entry** — if it needs a CHANGELOG, it belongs in formal memory.
- **Instructions or procedures** — instruction containment applies: only `core/memory/skills/` and `core/governance/` files may instruct. "Next time, do X" is a skill proposal candidate, not a scratchpad entry.
- **Content the user has asked to forget** — scratchpad is not a loophole around a forget request.
- **Content already ready for formal memory** — if it's ready, propose it; don't use scratchpad to avoid the governance process.
