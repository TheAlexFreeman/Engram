---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [schema, versioning, protobuf, avro, json-schema, compatibility, migration]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - ../testing/integration-testing-strategies.md
  - ../../self/_archive/2026-03-22-plan-schema-and-activity-logging-design.md
  - ../../mathematics/game-theory/evolution-of-cooperation.md
---

# Schema Evolution Strategies and Contract Versioning

The repository is approaching the point where informal schema evolution will stop being good enough. Frontmatter fields, ACCESS entries, and MCP payloads are now stable enough to deserve explicit compatibility rules. The good news is that mature systems already provide the patterns.

## Protocol Buffers show how stability depends on explicit identity

Protobuf's core lesson is not the binary encoding. It is that fields have stable identifiers and compatibility is judged against them.

Safe changes include:

- adding optional fields
- tolerating unknown fields on older readers

Unsafe changes include:

- reusing old meanings for existing identifiers
- changing semantics without a migration plan

For this repository, the analogous lesson is that field names and tool payload keys are contracts. Once published, their meaning cannot drift casually.

## Avro and schema registries formalize compatibility checks

Avro pushes a different but equally important idea: new schemas should be checked against previous ones under a declared compatibility policy.

That matters here because the repo currently has several evolving contracts at once:

- frontmatter schemas
- ACCESS entry schema
- MCP tool input and output shapes
- capability-manifest structure

Even a lightweight schema registry or compatibility table would be a major improvement over relying on memory and prose.

## JSON Schema and OpenAPI show the limits of prose-only versioning

JSON ecosystems often lean heavily on documentation and semantic versioning, but they do not automatically enforce compatibility. That is close to the repo's current situation.

The lesson is not that JSON Schema is weak. It is that human discipline alone is brittle once multiple tools and clients depend on the same payload shapes.

For MCP tools especially, a documented shape without automated compatibility checks is only partially a contract.

## Expand/contract is the migration pattern to prefer

The safest live-system migration pattern is:

1. expand: add the new field or behavior without removing the old
2. migrate: update writers and readers to understand the new form
3. contract: remove the old form only after consumers have moved

That pattern is directly applicable to the repo.

Examples:

- add `origin_commit` before treating it as required
- add `schema_version` to ACCESS records before enforcing version-aware parsing
- expose new tool result fields while keeping older fields intact during a transition window

## Versioning should exist at multiple layers

The system needs more than one version number.

Reasonable boundaries are:

- frontmatter schema version
- ACCESS schema version
- MCP contract version
- capabilities-manifest version

These should not all be collapsed into one repo-wide "format version" because they evolve at different speeds.

## Relevance to agent-memory-seed

This research changes several active plans materially:

- tool-improvement plans should treat new fields as expand/contract migrations, not as silent shape edits
- capability discovery should surface contract versions directly so clients can branch on them
- the runtime/package boundary work should centralize schema constants and compatibility tests instead of leaving semantics scattered across prose and code
- provenance-field additions should be versioned changes, not opportunistic metadata growth

The architectural takeaway is that the repository is moving from ad hoc conventions toward public contracts. At that point, compatibility policy becomes part of the product, not documentation garnish.

## Sources

- Protocol Buffers compatibility guidance
- Avro and schema-registry compatibility literature
- JSON Schema and OpenAPI evolution practices
