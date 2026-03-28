# Belief Diff Log

This file records periodic snapshots of how the memory system's content has changed over time. Each entry is generated during the 30-day periodic review cycle (see `core/governance/update-guidelines.md`) and provides a concise summary of drift since the previous entry.

## Purpose

The belief diff makes **drift visible**. A single malicious injection might be caught at write time, but slow-burn drift — many small, plausible changes that cumulatively shift agent behavior — is only detectable by comparing snapshots over time. If the user sees unexpected entries in this log, they can investigate and revert the relevant commits.

## Entry format

```
## [YYYY-MM-DD] Periodic review

### New files
- `path/to/file.md` — source: X, trust: Y, summary of content

### Modified files
- `path/to/file.md` — what changed and why

### Retired/archived files
- `path/to/file.md` — reason for retirement

### Trust changes
- `path/to/file.md` — trust: low → medium (reason)

### Security flags
- Summary of any anomalies or boundary violations detected since last review

### Identity drift
- Number of identity traits added/changed/removed
- Whether changes are consistent with observed user behavior

### Assessment
Brief overall assessment: is the system's evolution consistent with legitimate use, or are there patterns that warrant investigation?
```

---

## [2026-03-27] First belief diff — system creation through harness expansion

### New files
- `core/memory/users/Alex/profile.md` — source: agent-inferred, trust: medium, user portrait
- `core/memory/users/Alex/intellectual-portrait.md` — source: agent-inferred, trust: medium, intellectual profile
- `core/memory/knowledge/` — 6 domain trees created (software-engineering, philosophy, cognitive-science, ai, literature, plus subdomains). All source: agent-generated, trust: medium. Created via codebase-survey project.
- `core/memory/skills/onboarding.md` — rewritten from interview-style to collaborative seed-task flow
- `core/memory/skills/session-start.md`, `session-sync.md`, `session-wrapup.md` — session lifecycle procedures
- `core/memory/skills/eval-scenarios/` — 9 YAML eval scenario files covering plan lifecycle, verification, traces, approvals, tool policy, run state, and guardrails
- `core/memory/skills/tool-registry/` — YAML tool policy storage (shell.yaml seed data)
- `core/memory/working/projects/harness-expansion/` — 15-phase project, all phases completed
- `core/memory/working/projects/codebase-survey/` — 6-phase knowledge survey, pending promotion
- `core/memory/working/approvals/` — approval queue infrastructure (SUMMARY.md, pending/, resolved/)

### Modified files
- `core/governance/curation-policy.md` — split into curation-policy + content-boundaries + security-signals (consolidation Phase 3)
- `core/governance/session-checklists.md` — aligned with HOME.md-based returning-session contract
- `core/governance/first-run.md` — updated for collaborative onboarding redesign
- `README.md` — rewritten to document MCP server, session types, provenance model, updated repo structure

### Retired/archived files
- `core/memory/skills/_archive/onboarding-v1.md` — legacy interview-style onboarding, replaced by collaborative redesign

### Trust changes
- No trust promotions from low to medium or medium to high during this period (pending user review of codebase-survey outputs)

### Security flags
- No anomalies or boundary violations detected
- No external content ingested beyond codebase-survey self-analysis

### Identity drift
- Initial user profile created (not drift — baseline establishment)
- Identity traits consistent with observed behavior in onboarding session

### Assessment
System evolution is entirely consistent with legitimate initial setup and feature development. All changes trace to either the onboarding session (2026-03-18), governance consolidation (2026-03-22), documentation rewrites (2026-03-23–25), or the harness expansion project (2026-03-26–27). No suspicious patterns. The rapid pace of harness development (Phases 1-15 in ~2 days) reflects concentrated development effort, not injection.
