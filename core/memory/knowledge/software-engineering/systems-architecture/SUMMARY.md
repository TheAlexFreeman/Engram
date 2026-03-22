# Systems Architecture Knowledge — Summary

Research notes on the storage, concurrency, and automation primitives that underlie agent-memory-seed as a Git-backed memory system.

## Files

| File | Topics |
|---|---|
| `git-object-model.md` | Git object graph, index as staging boundary, lock-file semantics, refs, reflog, packfiles, and why the current MCP write path depends on them |
| `git-worktrees-and-hooks.md` | Linked worktree topology, per-worktree vs shared refs, orphan branches, bootstrap implications, hook execution model, and governance automation seams |
| `git-plumbing-and-automation.md` | Porcelain vs plumbing, explicit commit publication path, `update-ref`, `cat-file`, `notes`, `bundle`, sparse-checkout, and resilient scripting patterns |
| `filesystem-atomicity-and-locking.md` | `rename()` atomicity, `O_CREAT|O_EXCL`, advisory locks, unlink failure modes, `fsync()` durability, and why lockfile assumptions break on unusual mounts |
| `filesystems-for-developers.md` | Journaling vs copy-on-write filesystems, FUSE and network-share behavior, watcher caveats, and capability-tier thinking for stateful developer tools |
| `write-ahead-logging-and-wal-design.md` | WAL invariants, SQLite and PostgreSQL WAL behavior, Git staging as a mini-WAL, and staged-transaction requirements for multi-file MCP writes |
| `append-only-logs-and-compaction.md` | Log-structured storage, LSM/Kafka compaction ideas, event sourcing, archive segmentation, and ACCESS summary materialization |
| `concurrency-models-for-local-state.md` | Optimistic versus pessimistic control, version tokens as compare-and-swap, MVCC for derived SQLite state, and actor-model single-writer design |
| `crdts-and-collaborative-text.md` | CRDT guarantees and limits, Automerge/Yjs/OT comparison, and why governed Markdown files should prefer serialized writes over text convergence |
| `provenance-and-trust-models.md` | PROV-O, SLSA-style process trust, Biba integrity framing, and stronger provenance fields for governed memory artifacts |
| `temporal-data-modeling.md` | Transaction time versus valid time, verification-history trade-offs, event-time precision, and freshness modeling beyond date thresholds |
| `schema-evolution-strategies.md` | Protobuf/Avro compatibility lessons, expand-contract migrations, and explicit versioning boundaries for frontmatter, ACCESS, and MCP contracts |
| `content-addressable-storage-and-integrity.md` | CAS fundamentals, Git as a Merkle DAG, commit-SHA provenance, and integrity design grounded in Git's existing object model |

## Cross-references

- systems-architecture-research (historical plan reference) — the research plan these files satisfy (now complete)
- worktree-integration (historical plan reference) — downstream integration plan that depends on worktree/orphan-branch semantics
- [tools/agent_memory_mcp/git_repo.py](../../tools/agent_memory_mcp/git_repo.py) — current Git wrapper discussed throughout these notes (path will change after mcp-reorganization)