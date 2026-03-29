---
source: template
origin_session: setup
created: {{TODAY}}
trust: low
---

# Codebase Summary - {{PROJECT_NAME}}

This directory holds durable notes about the host repository at `{{HOST_REPO_ROOT}}`.

## Starter files

- [architecture.md](architecture.md) - Entry points, module map, and key dependencies.
- [data-model.md](data-model.md) - Core entities, persistence, and API boundaries.
- [operations.md](operations.md) - Run, test, deploy, and debug procedures.
- [decisions.md](decisions.md) - Design rationale, ADRs, and historical constraints.

## Usage notes

- These files start as low-trust templates and should be replaced with verified notes as the survey plan advances.
- Add `related` frontmatter as soon as a note is grounded in specific host-repo paths.
- Use `memory/working/projects/codebase-survey/plans/survey-plan.yaml` to decide which stub to replace next.
