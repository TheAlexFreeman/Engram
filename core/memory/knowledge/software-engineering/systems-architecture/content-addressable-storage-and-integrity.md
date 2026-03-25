---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [cas, integrity, merkle, git, commit-sha, provenance, verification]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - git-object-model.md
  - git-worktrees-and-hooks.md
  - provenance-and-trust-models.md
  - concurrency-models-for-local-state.md
---

# Content-Addressable Storage and Integrity

Git's most important architectural property is not version control in the abstract. It is content-addressable storage. The repository already relies on this implicitly through commits and version tokens, but several active plans would benefit from using that property much more directly.

## Content-addressable storage changes what identity means

In a content-addressable system:

- identical content yields the same address
- changed content yields a different address
- mutation becomes "create a new object and publish a new reference" rather than in-place overwrite

That is a stronger integrity model than path-based identity. Paths are names. Content hashes are evidence.

## Git is already a CAS with Merkle structure

Git stores blobs, trees, commits, and tags by hash. Commits point to trees and parent commits. Trees point to blobs and subtrees. That makes the repository a Merkle DAG.

Implications:

- any change to file content changes the blob hash
- that changes the tree hash
- that changes the commit hash
- child commits inherit the integrity chain through parent links

This is why commit SHAs are much stronger provenance anchors than session-path strings alone.

## Integrity checking is a first-class capability in CAS systems

CAS designs make verification natural because the address itself encodes expected content identity. In Git, commands such as `git fsck`, `git cat-file`, and ordinary object resolution already expose this model.

For this repo, the useful lesson is not to build a second integrity system from scratch when Git already provides one.

## Nix shows the stronger end of the same design spectrum

The Nix store is another strong example:

- packages are addressed by hashes of their build inputs
- reproducibility becomes a property of the address model
- upgrades are explicit moves to a new content-derived identity

The repo does not need Nix-level rigor, but the comparison helps clarify a gap: `origin_session` is not content-addressed. It is only a path reference into a session namespace.

## Commit SHA provenance would materially improve the current model

Several active plans would become more robust if they captured commit-level provenance explicitly.

Examples:

- a knowledge file about a codebase module could record the host commit or commit range it was verified against
- a session summary could record the commit at which it was created
- a promoted knowledge file could include the commit in which review occurred

Those fields would not replace human-readable paths. They would complement them with cryptographically meaningful anchors.

## Version tokens already hint at this design direction

The repository's version tokens are effectively lightweight CAS checks over current file content. That is a good sign. It means some of the design already thinks in content-addressed terms.

The next step is to extend the same idea from conflict detection into provenance and validation.

## Relevance to agent-memory-seed

This research has direct consequences for active plans:

- provenance-related tools should prefer commit-SHA capture where available, especially in worktree mode
- validation and integrity tooling should lean on Git's Merkle properties instead of inventing weaker path-only checks
- schema evolution should treat commit-anchored provenance as an additive, versioned enhancement
- freshness detection in host repos becomes much more precise when knowledge notes can say "verified against commit X" rather than only "verified on date Y"

The architectural takeaway is that the repository already sits on a strong integrity substrate. The missing move is to surface Git's content-addressed identity directly in its metadata and tooling.

## Sources

- Git object model and Merkle-DAG documentation
- Nix and content-addressable package-store literature
