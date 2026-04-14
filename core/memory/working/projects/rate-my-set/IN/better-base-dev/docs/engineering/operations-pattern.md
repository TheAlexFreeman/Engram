# Operations Pattern (Django)

## Purpose

Document the repository-level expectation for using an operations layer to organize
business logic as the system scales.

## Where Operations Live

Operations live in:

- `backend/**/ops.py`
- `backend/**/ops/**/*.py`

## Definition

An operation is an action-oriented unit of business logic that is callable from one or
more entry points (views, tasks, commands, etc.).

## Design Intent

- Keep models focused on data integrity and model-local behavior.
- Keep views/tasks/commands focused on adapting inputs and calling operations.
- Keep cross-model and side-effect-heavy workflows in operations.

## Public vs Private

- Public operation entrypoints are non-underscored.
- Internal-only helpers are underscored.

## Validate-Can Pattern

Prefer `validate_can_<action>` checks where this improves clarity between:

- state/permission validation, and
- action execution.

## Discoverability

The operations layer should function as a table of contents for domain actions. A new
engineer should be able to scan ops modules and quickly identify supported business
workflows.

## References

- Talk: https://www.youtube.com/watch?v=bs7XqSPN50M
- Local notes and transcript source:
- `Django Con 2024 Talk _ Micah Lyle _ Draft 09-19 _ Operations - The Missing Django Piece.txt`
- Skill guidance:
- `.agents/skills/operations/SKILL.md`
