---
created: 2026-04-08
next_question_id: 10
origin_session: memory/activity/2026/04/08/chat-001
source: agent-generated
trust: medium
type: questions
---

# Open Questions

## q-006: Where should the narrative/formal boundary be drawn for each skill?
**Asked:** 2026-04-09 | **Last touched:** 2026-04-09
Skills steer agents via narrative (prose guidance) and formal mechanisms (deterministic triggers, validators, state machines). The transcript analysis on narrative-vs-formal specification suggests skills should stay narrative for judgment and priorities, and formalize only where determinism is load-bearing (checkpoints, retries, audit). What conventions should Engram develop for when skill content should delegate to deterministic tooling vs. staying in prose? The trigger system is a good first formal layer — what comes next, and what should explicitly *not* be formalized?

## q-007: Should the graduation pipeline be bidirectional?
**Asked:** 2026-04-09 | **Last touched:** 2026-04-09
The existing design thesis is knowledge → skills → MCP tools (narrative → formal). But if formal control creates brittleness (agents failing on unanticipated inputs), that's a signal to relax back to narrative. Should the system support demotion as well as promotion, and what signals would trigger it?

## q-008: How should skill quality be evaluated ethnographically rather than as unit tests?
**Asked:** 2026-04-09 | **Last touched:** 2026-04-09
Narrative-specified behavior can't be validated with `assert output == expected`. The sidecar transcript system already captures raw session data. What would an eval harness look like that assesses whether a skill's narrative guidance produces good agent behavior *across sessions*, not just within one?

---

---

# Resolved Questions

## q-003: Should multi-agent distribution target specific tools (Claude, Cursor, Codex) or be extensible via a plugin pattern?
**Asked:** 2026-04-08 | **Last touched:** 2026-04-15
**Resolved:** 2026-04-15 | **Resolution:** Adopt a hybrid model: reserve a small built-in target set in the manifest (`engram`, `generic`, `claude`, `cursor`, `codex`) for interoperability, but implement distribution through target adapters so new tools can be added without changing manifest shape. Unknown target ids remain invalid unless an adapter is registered.

## q-004: What is the migration path for existing vaults that have skills checked into git today?
**Asked:** 2026-04-08 | **Last touched:** 2026-04-15
**Resolved:** 2026-04-15 | **Resolution:** Use an incremental migration path. Existing vaults can keep `defaults.deployment_mode: checked` and continue committing all skills unchanged. Repos that want lower-noise deployment can opt in gradually by removing the repo-wide default to enable trust-aware fallback or by setting `deployment_mode: gitignored` only on selected skills; install/sync then restores those skills locally from manifest and lock state.

## q-001: Should the manifest format be TOML (like dotagents) or YAML (consistent with existing Engram conventions)?
**Asked:** 2026-04-08 | **Last touched:** 2026-04-15
**Resolved:** 2026-04-15 | **Resolution:** Use YAML for the canonical skill manifest. Engram already governs most durable memory artifacts as human-readable YAML frontmatter or YAML documents, so `SKILLS.yaml` fits existing editing and validation flows better than introducing a TOML-only island. The dotagents influence remains architectural rather than syntactic: adopt package-manager ideas such as declarative manifests, lockfiles, and source pins, but express them in Engram’s existing YAML conventions.

## q-002: How should skill versioning interact with Engram's existing trust model — does pinning a version imply trust:high?
**Asked:** 2026-04-08 | **Last touched:** 2026-04-15
**Resolved:** 2026-04-15 | **Resolution:** No. Version pinning and trust answer different questions. `ref`, `requested_ref`, and `resolved_ref` capture reproducibility and supply-chain determinism; `trust` remains a separate declaration that must match SKILL.md frontmatter and still flows through governed trust updates. A pinned remote skill can still be `medium` or `low` trust if the content is reproducible but not yet socially verified.

## q-005: Should the skill registry be centralized (like npm) or federated (like git remotes)?
**Asked:** 2026-04-08 | **Last touched:** 2026-04-15
**Resolved:** 2026-04-15 | **Resolution:** Prefer a federated model rooted in git and local path sources, not a centralized registry. The manifest now supports `github:`, `git:`, `path:`, and `local` sources, with lockfile capture for reproducibility. That keeps publishing and consumption aligned with Engram’s git-native design while still allowing a future registry layer to exist as an optional convenience rather than a required authority.

## q-009: How should fresh-clone recovery handle gitignored skills whose manifest source is `local` (including template-created low-trust skills), given that `SKILLS.lock` records hashes and refs but not the skill contents needed to reconstruct them?
**Asked:** 2026-04-15 | **Last touched:** 2026-04-15

---
**Resolved:** 2026-04-15 | **Resolution:** Adopt a source-aware deployment rule: manifest entries with source `local` must remain `checked` because their contents are not reconstructible from `SKILLS.lock` on a fresh clone. Explicit `deployment_mode: gitignored` is invalid for `source: local`; use `path:`, `git:`, or `github:` sources when a skill should be restored on demand instead of committed.