# Operations Pattern Whitepaper Notes

This document captures the Operations pattern context provided for this repository.

## Source Materials

- Original talk: https://www.youtube.com/watch?v=bs7XqSPN50M
- Gemini summary link: https://gemini.google.com/share/92d320358c09
- Local slide transcript text:
- `Django Con 2024 Talk _ Micah Lyle _ Draft 09-19 _ Operations - The Missing Django Piece.txt`

## Problem Statement

As Django apps scale, business logic often drifts into:

- oversized model methods,
- view-level duplication,
- poor discoverability of what the system can actually do.

This produces maintenance drag and weak onboarding ergonomics.

## Operations Layer

Operations are action-oriented business logic units that live in `ops.py` or
`ops/**/*.py`. They are intentionally framework-entrypoint agnostic, so they can be
called from views, tasks, commands, and other operations.

### Practical boundary

- Model methods: model-local behavior and invariants.
- Operations: cross-model orchestration and domain workflows.
- Entry points: input/auth/permissions adapters that call operations.

## Four Rules (Repo-Adapted)

1. Object-agnostic: an operation can be a function, class, method, decorator, or
   context manager.
2. Location-specific: operation entrypoints live under `ops.py` or `ops/` paths.
3. Public/private: public operations are non-underscored; private helpers are
   underscored.
4. Action-oriented: operations do work; data-only types are support structures, not
   operations.

## Validate-Can Pattern

Use `validate_can_<action>` style checks to separate:

- "Can this be done?" validation/permission/state checks
- from
- "Do it" execution logic.

This improves readability, testability, and review quality.

## Folder-Structure Note

Any folder-structure examples in this doc are specifically about organizing the
operations layer. They are not blanket mandates for all project modules.
