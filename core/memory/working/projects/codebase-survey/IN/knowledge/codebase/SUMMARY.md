---
source: template
origin_session: setup
created: 2026-03-23
trust: low
---

# Codebase Summary - Engram

This directory holds durable notes about the Engram host repository.

## Starter files

- [architecture.md](architecture.md) - Entry points, module map, and key dependencies.
- [data-model.md](data-model.md) - Core entities, persistence, and API boundaries.
- [operations.md](operations.md) - Run, test, deploy, and debug procedures.
- [decisions.md](decisions.md) - Design rationale, ADRs, and historical constraints.

## Usage notes

- These files start as low-trust templates and should be replaced with verified notes as the survey plan advances.
- Add `related` frontmatter as soon as a note is grounded in specific host-repo paths.
- Use `plans/survey-plan.yaml` (relative to project root) to decide which stub to replace next.
- Once a file reaches medium trust, promote it from IN/ to `knowledge/codebase/` via OUT/.
