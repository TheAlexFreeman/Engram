---

source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [filesystem, atomicity, rename, locking, o-excl, flock, fsync, durability, fuse, nfs]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - append-only-logs-and-compaction.md
  - filesystems-for-developers.md
  - concurrency-models-for-local-state.md
---

# Filesystem Atomicity, Locking, and Durability

The `index.lock` failure that motivated this research is not really a Git problem. It is a filesystem-contract problem that surfaced through Git. If the MCP server is going to remain reliable across local disks, sandboxed mounts, Windows, and network filesystems, it needs a sharper model of what the OS actually promises.

## `rename()` is the standard atomic replace primitive

On POSIX-style systems, `rename(old, new)` provides the core safe-replacement guarantee used by Git and many databases.

The key guarantee is:

- if `new` already exists, it is atomically replaced
- observers should not see a moment where `new` simply vanishes
- open file descriptors to the old object remain valid

That is why the classic safe-write pattern is:

1. write new contents to a temporary file
2. flush that file as needed
3. rename the temporary file over the destination

Git uses this pattern for mutable administrative files such as the index. The atomic commit point is not "write bytes into the target file." It is the final rename.

Important caveats:

- `rename()` is only atomic within the same mounted filesystem; cross-filesystem rename fails with `EXDEV`
- NFS failure modes are weaker than local-disk assumptions; a failed rename does not always prove the rename did not happen
- overlay or union filesystems may add whiteout and copy-up semantics that complicate intuition

So `rename()` is the right primitive, but only within its real scope.

## Why lock files use `O_CREAT | O_EXCL`

The other half of the pattern is safe lock acquisition. `open(path, O_CREAT | O_EXCL, ...)` means:

- create the file if it does not already exist
- fail atomically with `EEXIST` if it already exists

That avoids the classic race in "check whether lock file exists, then create it." Two processes cannot both win the same exclusive create.

This is why Git's lock-file strategy is sensible:

- claim exclusive intent with `index.lock`
- write new state there
- publish with `rename()`

The important point is that the filesystem is being used as a coordination substrate. If the mount weakens or breaks those semantics, lock discipline collapses.

## Why this is better than test-then-create

Any sequence like:

1. `stat()` the lock file
2. if missing, create it

has a time-of-check/time-of-use race. Another process can create the file between those steps.

`O_CREAT | O_EXCL` pushes the check and create into one kernel operation. That is the only reason lock files are trustworthy at all.

## Advisory locking versus lock files

POSIX systems also offer advisory locking APIs such as `flock()` and `fcntl()` byte-range locks.

`flock()` gives:

- `LOCK_SH` shared locks
- `LOCK_EX` exclusive locks
- `LOCK_NB` nonblocking acquisition

But these are advisory locks. A cooperating process will check and respect them; a non-cooperating process can ignore them and still write the file if permissions allow.

That makes them useful inside a coordinated application ecosystem, but not sufficient as a universal protection boundary.

Lock files and advisory locks solve slightly different problems:

- lock files are visible state in the filesystem namespace
- advisory locks are kernel-managed state associated with open file descriptions

Git's index-lock pattern uses the namespace approach because it is portable and explicit.

## Advisory locks are not uniform across filesystems

The semantics of `flock()` and `fcntl()` vary more than many developers assume:

- on Linux local filesystems, `flock()` is advisory and tied to the open file description
- on NFS, `flock()` may be emulated via `fcntl()` byte-range locks
- on SMB/CIFS, lock behavior may become mandatory rather than advisory

That matters for any future MCP-server locking design. If the goal is "prevent my own cooperating agents from colliding," advisory locks can help. If the goal is "guarantee mutation exclusion across arbitrary tooling and odd filesystems," they are not enough by themselves.

## Why `unlink()` can fail even when you "own" the file

The lock-file incident specifically involved cleanup failure. That is plausible for several reasons:

- insufficient write or search permissions on the containing directory
- sticky-bit rules on a shared directory
- immutable flags or filesystem-specific protection features
- read-only mounts
- FUSE or sandbox policies that virtualize or restrict unlink semantics

This is the critical mindset shift: deleting a file is primarily a directory-mutation operation, not a property of the file alone. Being able to read or even write the file does not guarantee you can unlink its directory entry.

For Git, a lock file that cannot be removed is effectively a transaction that never completed.

## Durability is a separate problem from atomic visibility

Atomic rename answers "what do concurrent readers observe?" It does not by itself answer "will the new state survive a crash?"

That is where `fsync()` and `fdatasync()` matter.

- `fsync(fd)` flushes file data and relevant metadata for that file to stable storage
- `fdatasync(fd)` skips metadata not needed for future reads
- to guarantee the directory entry itself is durable, the directory also needs its own `fsync()`

This is a commonly missed point. If you write a temp file, `fsync()` it, rename it, and then crash before the parent directory entry is flushed, you may still lose the rename after reboot depending on filesystem behavior.

That is why databases and carefully written storage engines treat directory sync as part of the commit protocol.

## Why this matters even for a Git-backed Markdown repo

Today this repository is not trying to be SQLite. But the moment it claims governed, crash-tolerant, multi-file writes, the same durability questions appear.

Examples:

- staging several files and committing them together
- updating `SUMMARY.md` plus a data file plus `ACCESS.jsonl`
- creating or rotating archive files

If the design assumes close-to-disk durability without understanding when the OS actually flushes data and metadata, it is making promises the platform may not keep.

## FUSE and sandboxed mounts are exactly where assumptions break

FUSE filesystems sit between the kernel VFS layer and a userspace daemon. That extra layer means some operations that are "basically always fine" on ext4 or APFS can degrade, fail, or exhibit different performance characteristics.

Relevant risks include:

- weaker or unusual unlink behavior
- rename semantics that are technically supported but slower or more failure-prone
- permission models that differ from a normal local mount
- partial support for locking behavior

That makes the original `index.lock` incident unsurprising in retrospect. Git assumed a normal filesystem contract. The environment did not fully behave like one.

## Network filesystems are worse for coordination than local disks

The Linux man pages are explicit that NFS weakens some of the assumptions around `O_EXCL`, append, and rename failure interpretation.

Practical implications:

- lock-file strategies may race on older or misconfigured NFS setups
- append-only logs can still experience coordination problems
- remote event visibility is not equivalent to local event visibility
- durability claims may depend on server behavior, not just the client kernel

Any production-readiness story for this system needs to distinguish local-disk-supported behavior from network-filesystem-best-effort behavior.

## Implications for agent-memory-seed

This research sharpens several design decisions:

- The current Git wrapper depends on the filesystem honoring Git's lockfile protocol.
- A resilient fallback path may need to avoid the standard index-update workflow when lock cleanup is unreliable.
- Future direct-file transaction logic should use temp-write plus rename, and treat directory sync as a separate concern when durability actually matters.
- Environment validation should detect known-risk mounts and downgrade guarantees rather than pretending all filesystems are equal.

## Working rule for this repo

Treat these as different layers of guarantee:

- `rename()` gives atomic namespace switch, usually only within one filesystem
- `O_CREAT | O_EXCL` gives atomic lock acquisition if the underlying filesystem supports it correctly
- advisory locks give cooperative exclusion, not universal exclusion
- `fsync()` gives file durability, not automatic directory-entry durability

That layered model is the right lens for the next architectural steps.

## Sources

- Linux man pages: `rename(2)`, `open(2)`, `flock(2)`, `fsync(2)`
- Active plan context in systems-architecture-research (historical plan reference)