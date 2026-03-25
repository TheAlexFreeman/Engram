---

source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [filesystem, journaling, copy-on-write, fuse, inotify, nfs, smb, apfs, ext4, windows]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - filesystem-atomicity-and-locking.md
  - append-only-logs-and-compaction.md
  - git-object-model.md
  - concurrency-models-for-local-state.md
---

# Filesystems for Developers Building Stateful Tools

The memory system currently behaves as if "the filesystem" were one uniform substrate. In practice, local journaling filesystems, copy-on-write filesystems, FUSE mounts, network shares, and Windows-backed environments differ enough that architecture decisions should be made against filesystem classes, not against a generic abstraction.

## Journaling filesystems: protect metadata first

Traditional journaling filesystems such as ext4 and NTFS record pending metadata updates in a journal so recovery after a crash can restore consistency.

What journaling typically buys you:

- the filesystem structure is less likely to be corrupted after power loss
- operations like rename and directory updates are recoverable more cleanly
- metadata consistency is usually prioritized over application-level transaction semantics

What it does not buy you automatically:

- your application-level multi-file update is atomic
- every recently written byte has reached stable media
- cross-file invariants are preserved after a crash

For this repo, journaling means Git objects and directory structure are usually safer than naive file I/O would suggest, but it does not remove the need for explicit atomic-update patterns.

## Copy-on-write filesystems: overwrite becomes indirection

Copy-on-write filesystems such as APFS, btrfs, and ZFS avoid overwriting existing blocks in place. Instead they write new blocks and then update metadata pointers.

This enables:

- snapshots
- checksumming and stronger integrity features
- cleaner crash recovery properties for many update patterns

But it also changes performance intuition. Rewriting a file does not necessarily mean mutating the same physical blocks, and metadata behavior can be more complex than on classic journaling filesystems.

For agent-memory-seed, the design lesson is straightforward: temp-write plus rename still makes sense, but the cost and persistence behavior can differ meaningfully by filesystem family.

## APFS, ext4, and NTFS are not interchangeable in practice

From a developer's point of view:

- ext4 is the common Linux baseline for local POSIX-like semantics
- APFS gives Apple-specific copy-on-write behavior and strong rename/save patterns
- NTFS has different locking, sharing, and path-behavior semantics, especially when observed through POSIX-compatibility layers

On Windows environments, that point matters directly. Tools may expose a Unix-like shell while operating through translation layers over NTFS semantics. Any repo feature that assumes pure POSIX behavior should be tested rather than presumed in any POSIX-compatibility-layer environment.

## FUSE filesystems: user-space mediation changes the contract

FUSE routes filesystem operations through a user-space daemon. That creates flexibility, but it also introduces variation in behavior and latency.

Typical implications:

- extra context switches and worse small-operation latency
- edge-case differences in unlink, rename, and permission semantics
- weaker assumptions around locking and cache visibility
- behavior that is implementation-specific rather than purely kernel-defined

This matters because sandboxed development platforms often present a FUSE-like or virtualized filesystem surface. The earlier `index.lock` incident fits that profile exactly: a path that is "just a file" from the application's perspective may have policy or implementation behavior underneath that breaks Git's normal expectations.

## Event watching with inotify is useful but not equivalent to truth

Linux's inotify API lets a process watch files or directories for events such as:

- create
- delete
- modify
- move-from and move-to
- close-after-write

It is attractive for freshness detection and host-repo change tracking. But the man page surfaces important caveats:

- monitoring is not recursive by default
- event queues can overflow
- rename pairing via cookies is inherently racy
- network filesystem events are not reliably captured
- filenames can already be stale by the time events are processed

So inotify is best treated as an incremental hint stream, not a complete source of truth. Any worktree-integration freshness design should pair watchers with occasional reconciliation scans.

## Rename detection is especially tricky

inotify exposes `IN_MOVED_FROM` and `IN_MOVED_TO` with a shared cookie, which looks clean on paper. In practice:

- the pair may not be read atomically
- unrelated events can appear between them
- one half of the pair may be absent if the move crosses watch boundaries

That means any "keep cached path graph perfectly current from watcher events alone" design will be brittle. Rebuild and repair paths need to be part of the architecture.

## Network filesystems are coordination-hostile by default

NFS and SMB/CIFS are not just slower disks over the network. They have different coherence, locking, and visibility properties.

Practical risks include:

- client-side emulation of append or locking semantics
- weaker guarantees around immediate visibility across machines
- nonlocal durability behavior depending on server policy
- event-watch gaps or outright absence of useful watcher semantics

For this project, that means a repo on a network share should be treated as a degraded-capability environment unless proven otherwise.

## Why this matters for the worktree plan

The `worktree-integration.md` roadmap includes freshness detection against host codebases. That problem is easy to underestimate.

On a local Linux filesystem, one might combine:

- `inotify` for fast incremental hints
- periodic rescans for correctness
- `git`-aware checks where applicable

On a network share or virtualized mount, watchers may be incomplete or misleading. The system should therefore prefer a capability-tier model:

- strong local-watch mode on supported local filesystems
- poll-and-reconcile mode on weak or remote filesystems

That is a better design than pretending one watcher strategy fits all environments.

## What a validator should eventually check

This research suggests several useful environment checks for future validation tooling:

- is the repo on a local disk, network mount, or virtualized/sandboxed mount?
- are atomic rename and lockfile operations behaving normally?
- is the environment Windows-native, WSL, or POSIX-native?
- are watcher APIs available and trustworthy enough for incremental freshness?

Those checks would let the tool surface degraded guarantees early, instead of learning them from production failures.

## Developer-level mental model

For this repository, treat filesystems in four broad buckets:

- local journaling filesystems: good default substrate, still not application transactions
- local copy-on-write filesystems: strong local behavior, different performance and persistence intuition
- FUSE or sandboxed virtual filesystems: potentially surprising semantics, validate assumptions explicitly
- network filesystems: weakest coordination substrate, plan for degraded guarantees and reconciliation

That is the right abstraction level for a Git-backed stateful tool.

## Sources

- Linux man page: `inotify(7)`
- Linux man pages: `open(2)`, `rename(2)`, `flock(2)`, `fsync(2)`
- Git documentation for `git-worktree`