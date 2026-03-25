---
created: 2026-03-19
domain: systems-architecture
last_verified: 2026-03-19
origin_session: core/memory/activity/2026/03/19/chat-001
related:
  - git-plumbing-and-automation.md
  - git-worktrees-and-hooks.md
  - ../testing/model-checking-abstract-interpretation.md
source: external-research
tags:
- git
- object-model
- blobs
- trees
- commits
- tags
- index
- refs
- reflog
- packfiles
- storage
trust: medium
type: knowledge
---

# Git Object Model and Why It Matters Here

Git is best understood as a content-addressed object store with a version-control interface on top. That framing matters for this repository because the MCP server is not writing arbitrary files and then asking Git to bless them after the fact. It is interacting with a storage system that has a specific data model, a staged transition boundary, and explicit atomicity points.

## The four object types

Git's persistent storage revolves around four object types:

- `blob`: raw file content, with no filename attached
- `tree`: a directory snapshot containing entries for blobs, subtrees, symlinks, or submodules
- `commit`: a history node pointing at one top-level tree plus zero or more parent commits
- `tag`: a named object that usually points at a commit and adds tagger metadata plus a message

Every object is stored as `"<type> <size>\0<content>"`, hashed, then compressed with zlib before being written into `.git/objects/`. Historically that hash is SHA-1; newer Git configurations can use SHA-256 repositories, but the content-addressable model is the same.

The practical consequence is that Git does not primarily store diffs. It stores snapshots composed out of immutable objects, and later optimizes storage with packing and delta compression.

## Blobs, trees, and commits as a graph

A blob only stores bytes. If two files in different directories have identical content, they can point to the same blob object.

A tree stores entries of the form:

- mode
- object type
- object id
- filename

That means filenames live in trees, not in blobs. A commit then points at a top-level tree and records:

- parent commit ids
- author and committer identity
- timestamps
- message

So a commit is not "the files." It is a pointer to the root tree of a snapshot plus history metadata.

## The index is the load-bearing intermediate state

The staging area, stored in `.git/index`, is Git's mutable bridge between the working tree and the immutable object database.

Conceptually:

1. `git add` hashes file content into blob objects when needed.
2. Git updates the index entries to point at those blobs and record mode/stat metadata.
3. `git commit` turns the current index state into tree objects.
4. Git writes a commit object that points at the new top-level tree.
5. Git moves the relevant ref so the new commit becomes reachable.

That means the index is not bookkeeping noise. It is the place where Git assembles the next snapshot before it becomes history.

The current MCP implementation reflects that model directly. In [tools/agent_memory_mcp/git_repo.py](../../../../tools/agent_memory_mcp/git_repo.py), `add()` shells out to `git add`, and in tools/agent_memory_mcp/git_repo.py, `commit()` shells out to `git commit -m`. The server is therefore dependent on the index path working correctly.

## What `git add` actually does

At a low level, `git add` is roughly:

1. Read file bytes from the working tree.
2. Hash them into a blob object if the exact content is not already present.
3. Update the index entry for that path with object id, mode, and cached filesystem metadata.

The Git plumbing equivalents make this explicit:

- `git hash-object -w --stdin` writes the blob
- `git update-index --add --cacheinfo ...` records the blob in the index
- `git write-tree` materializes a tree from the index
- `git commit-tree` creates a commit pointing at that tree
- `git update-ref` moves a branch ref to the new commit

That low-level sequence matters because it reveals which steps truly require the index and which can be bypassed.

## Why Git uses `index.lock`

The index is mutable shared state, so Git cannot safely rewrite it in place with no coordination. The standard pattern is:

1. Create `.git/index.lock`
2. Write the new index contents there
3. `rename()` the lock file into place as `.git/index`
4. Remove the lock artifact

The lock file creation uses an exclusive-create pattern at the OS level so two Git processes cannot both believe they own the index mutation. This is the same general strategy databases and editors use for safe replace-on-write.

If the lock file cannot be created, Git assumes another process may be writing the index. If the lock file cannot be cleaned up or renamed into place, the index update fails. That is exactly why index-lock issues are catastrophic for any workflow built on `git add`.

## The failure mode this repo actually cares about

The plan cites a sandboxed filesystem incident where index operations failed because the lock file could not be unlinked or finalized cleanly. That is not an edge case for theory's sake; it is a direct architectural constraint.

In this repository, the Git wrapper currently assumes the porcelain path is reliable:

- `add()` depends on index mutation succeeding
- `add_all()` depends on `git add -A`
- `commit()` assumes staged state is available

If `.git/index.lock` becomes unwritable, undeletable, or otherwise stuck due to FUSE or sandbox semantics, the write surface is effectively down even when blob writes and ref updates might still be possible. The object model explains why: the current implementation depends on the index as its only assembly point.

## Loose objects, packfiles, and long-term growth

Freshly written objects are usually stored as loose objects under `.git/objects/aa/bb...`. Over time Git consolidates them into packfiles under `.git/objects/pack/`.

Packfiles improve storage and read efficiency by:

- grouping many objects into one binary pack
- keeping an index file for object lookup
- delta-compressing similar objects, often against newer versions

This matters for agent-memory-seed because the repository is expected to accumulate many small markdown objects over time, plus repeated rewrites of summary and plan files. The storage layer will stay functional, but maintenance behavior like `git gc`, repacking frequency, and packfile locality will increasingly shape performance characteristics.

Important nuance: Git's logical model is immutable snapshots, but physical storage is opportunistically compacted. The repo's behavior under scale depends on both.

## Refs, symbolic refs, and reflog

Git refs are named pointers into the object graph. Common examples:

- `refs/heads/<branch>` for local branches
- `refs/remotes/<remote>/<branch>` for remote-tracking branches
- `refs/tags/<name>` for tags

`HEAD` is usually a symbolic ref containing something like `ref: refs/heads/core`. In detached-HEAD state it instead contains a raw object id.

The important distinction is:

- ordinary refs usually point directly to object ids
- symbolic refs point to another ref name

The reflog then records how refs moved over time, which gives a recovery trail even when names are updated destructively.

For a memory system built on Git, reflog is operationally important because accidental ref movement, bad rebases, or incorrect branch initialization are often recoverable even when the branch tip has moved.

## Why this clarifies the MCP atomicity problem

One tempting but incorrect mental model is: "the server writes files, then commits them atomically." Git's actual model is stricter:

- files are ordinary working-tree state
- the index is the staged candidate snapshot
- tree objects are derived from that index
- the commit object captures the tree plus parents and metadata
- the branch ref update is the final publication step

So the staging step is not optional boilerplate. It is the mechanism that turns mutable working-tree bytes into a stable next snapshot.

That is why tools/agent_memory_mcp/git_repo.py and tools/agent_memory_mcp/git_repo.py are more than simple shell wrappers: they encode the current transaction model of the whole system.

## Architectural relevance for future work

This file sharpens several design directions in the active plan set:

- A resilient write path may need a plumbing-based commit flow that can avoid normal index mutation in degraded environments.
- Worktree integration depends on understanding shared refs versus per-worktree pseudo-refs.
- Governance automation that relies on "just commit everything together" must respect the index as Git's real snapshot boundary.
- Storage scaling questions for ACCESS logs and summaries are not just filesystem questions; pack and ref behavior matter too.

The root lesson is simple: Git is not a fancy file-copy tool. It is an object database with a staging transaction boundary, and this repository's reliability depends on treating it that way.

## Sources

- Pro Git, "Git Internals - Git Objects"
- Pro Git, "Git Internals - Git References"
- Pro Git, "Git Internals - Packfiles"
- Repository code in tools/agent_memory_mcp/git_repo.py
