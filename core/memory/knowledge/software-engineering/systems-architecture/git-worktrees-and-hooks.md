---
created: 2026-03-19
domain: systems-architecture
last_verified: 2026-03-19
origin_session: core/memory/activity/2026/03/19/chat-001
related:
- memory/knowledge/software-engineering/systems-architecture/git-object-model.md
- memory/knowledge/software-engineering/systems-architecture/git-plumbing-and-automation.md
- memory/knowledge/software-engineering/systems-architecture/provenance-and-trust-models.md
- memory/knowledge/software-engineering/systems-architecture/append-only-logs-and-compaction.md
- memory/knowledge/software-engineering/systems-architecture/filesystem-atomicity-and-locking.md
source: external-research
tags:
- git
- worktrees
- orphan-branches
- hooks
- refs
- governance
- automation
trust: medium
type: knowledge
---

# Git Worktrees, Orphan Branches, and Hooks

This repository already uses `git worktree` operationally during revert preview, and one of the active plans proposes installing the memory system into host projects via orphan branch plus worktree. That makes worktree topology and hook execution semantics first-order architectural concerns rather than background Git trivia.

## What a linked worktree actually is

`git worktree add` creates an additional working tree attached to the same repository. Git calls the original checkout the main worktree and each extra checkout a linked worktree.

The important sharing model is:

- shared across worktrees: object store, most refs, remotes, common config
- per worktree: `HEAD`, index, working tree contents, some pseudo-refs, optional worktree-specific config

Under the hood, Git records linked-worktree metadata under `$GIT_COMMON_DIR/worktrees/<name>/`. Inside the linked checkout, the top-level `.git` is not a directory; it is a file pointing back to that administrative area.

That means a worktree is not a clone. It is another checkout view over the same underlying object database.

## Shared refs versus per-worktree refs

The official worktree docs make a crucial distinction:

- pseudo-refs like `HEAD` are per-worktree
- refs under `refs/` are shared, except special namespaces such as `refs/bisect`, `refs/worktree`, and `refs/rewritten`

This matters because a design that assumes every branch-like name is local to one worktree will be wrong. Branch refs are usually shared. `HEAD` is not.

For agent-memory-seed, this means:

- branch naming and publication strategy are shared-state concerns
- per-worktree status inspection must not assume `HEAD` lives in the common gitdir
- path inspection should prefer `git rev-parse --git-path ...` over hard-coded filesystem assumptions

## The repo already depends on worktree behavior

The current revert preview implementation in [tools/agent_memory_mcp/git_repo.py](../../../../tools/agent_memory_mcp/git_repo.py) creates a detached temporary worktree, runs `git revert --no-commit`, then removes the worktree. That code already relies on linked-worktree semantics:

- shared object store so the preview can see repository history cheaply
- isolated `HEAD` and index so the preview does not contaminate the main checkout
- clean teardown via `git worktree remove --force`

So the system is not merely planning to use worktrees. It already treats them as a safe isolation primitive.

## Orphan branches and why they fit the memory-store use case

An orphan branch is a branch whose first commit has no parent. The practical effect is separate history with shared object storage.

Typical usage is `git checkout --orphan <name>` or, in modern worktree flows, `git worktree add --orphan <name> <path>`.

The important properties are:

- the branch starts unborn, with no parent commit
- once the first commit is created, that commit becomes a new root
- the repository still shares the same object database as other branches
- history is separate even though storage is shared

That is exactly why orphan-branch worktree integration is attractive for this project. The memory system can live as a separate line of history without polluting the host project's main commit graph, while still sharing one `.git` object store and one remote topology.

## `--no-checkout` and seed-time customization

`git worktree add --no-checkout` suppresses populating the working tree immediately. That is valuable when initialization needs to:

- install sparse-checkout settings first
- place seed files before a normal checkout
- prepare worktree-specific configuration before content materialization

For a bootstrap script such as the one proposed in `worktree-integration.md`, `--no-checkout` is a useful lever because it keeps initialization deterministic instead of mixing seeding logic with Git's default checkout behavior.

## Hooks: where automation actually runs

Hooks are executable programs placed in `$GIT_DIR/hooks/` unless `core.hooksPath` redirects them elsewhere. Their execution model matters:

- in non-bare repos, most hooks run with the working directory at the worktree root
- in bare repos and push-side receive hooks, they run in `$GIT_DIR`
- Git exports environment variables such as `GIT_DIR` and `GIT_WORK_TREE`

This makes hooks a practical boundary-crossing mechanism between repository events and governance automation.

## Client-side hooks most relevant here

For this repository's needs, the highest-value hooks are:

- `pre-commit`: block commits that violate frontmatter or repo invariants
- `commit-msg`: enforce commit-message conventions if desired
- `post-commit`: trigger lightweight freshness or maintenance signals after a successful commit
- `post-checkout`: initialize worktree-local metadata or MCP config after branch/worktree switches
- `post-merge`: restore derived metadata or rerun validation after merges
- `pre-push`: stop remote publication when validation fails

Two details matter:

- `pre-commit` and `commit-msg` can abort the underlying Git command on non-zero exit
- `post-commit` and `post-checkout` are notification-style hooks and cannot prevent the completed action

That distinction should drive design. Hard invariants belong in pre-hooks. Follow-up maintenance belongs in post-hooks.

## How hooks interact with worktrees

Hooks live in the common Git administrative area, not separately inside each linked checkout by default. That means a hook configuration applies across worktrees unless deliberately redirected.

That is powerful but dangerous:

- good because validation logic can be shared across all memory worktrees
- risky because hooks may assume paths or environment details that only hold in one checkout

Any hook introduced for worktree-based memory branches needs to be path-aware and should derive repository paths using Git commands rather than assumptions about `.git` being a directory in the local checkout.

## Why `post-checkout` is especially relevant

The official docs note that `post-checkout` also fires after `git worktree add` unless `--no-checkout` is used. That creates a clean bootstrap seam.

Possible uses in this system:

- install or validate local MCP config when a memory worktree is created
- refresh codebase-knowledge symlinks or adapter files
- warn when a worktree is missing required validation scripts
- surface branch-role information to the user or agent

Because `post-checkout` cannot block the checkout itself, it is better used for idempotent repair and initialization than for hard policy enforcement.

## Why `pre-commit` remains the real policy gate

The plan specifically mentions `validate_memory_repo.py` as a pre-commit enforcement target. That is the right hook if the goal is to stop invalid frontmatter, forbidden path mutations, or malformed summaries before they land in history.

This solves a real weakness in the current operating model: many governance rules only work when the agent remembers to run them. Hooks convert remembered procedure into repository-enforced behavior.

## Design constraints surfaced by worktree docs

The worktree documentation exposes a few concrete constraints for the integration roadmap:

- moving worktrees manually can break linkage; bootstrap docs should recommend `git worktree move` or `repair`
- portable-device or network-share worktrees may need `git worktree lock`
- worktree-specific configuration should use `extensions.worktreeConfig` and `git config --worktree` when settings must differ by checkout
- scripts should use `git worktree list --porcelain` for machine parsing rather than human-format output

These are not polish details. They are the difference between a robust integration and one that breaks the first time a path changes.

## Architectural relevance for active plans

This file directly informs `worktree-integration.md`:

- Phase 0: init script design needs orphan-branch and `--no-checkout` clarity
- Phase 1: adapter and MCP config placement need worktree-specific config strategy
- Phase 2: freshness detection and host-repo visibility need correct path and ref semantics
- governance automation: hook selection should separate blocking validation from post-action maintenance

It also reinforces a broader lesson for the MCP server: worktrees are the right isolation primitive when the system needs another checkout without another clone.

## Sources

- Git documentation, `git-worktree`
- Git documentation, `githooks`
- Repository code in tools/agent_memory_mcp/git_repo.py
