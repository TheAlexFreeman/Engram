---
source: external-research
origin_session: core/memory/activity/2026/03/19/chat-001
type: knowledge
domain: systems-architecture
tags: [provenance, trust, prov-o, slsa, biba, integrity, governance]
trust: medium
created: 2026-03-19
last_verified: 2026-03-19
related:
  - concurrency-models-for-local-state.md
  - ../../mathematics/causal-inference/structural-causal-models-dags.md
  - ../../ai/frontier/alignment/rlhf-reward-models.md
---

# Provenance and Trust Models

The repository already has a distinctive trust model, but it is still mostly bespoke. That is workable in a seed repo, yet the active implementation plans are now close enough to governance-runtime work that a more explicit provenance vocabulary would pay off.

## PROV-O provides the cleanest vocabulary for "where did this come from"

W3C PROV-O organizes provenance around three core concepts:

- Entity: the artifact or record
- Activity: the process that produced or changed it
- Agent: the person or system responsible

The current frontmatter partially encodes this already:

- the file itself is an Entity
- `origin_session` points loosely toward an Activity
- `source` hints at the Agent or production mode

What is missing is a clearer distinction between:

- who produced the artifact
- in what process it was produced
- which prior artifacts it depended on

That missing distinction is the reason provenance is currently informative but not yet very queryable.

## SLSA is a useful analogy for trust levels

SLSA asks not only what an artifact is, but how trustworthy its build process was. The same perspective helps here.

The repo's current trust levels are content-centric. SLSA suggests a process-centric refinement:

- a note hand-written by the user and reviewed may deserve stronger trust than one generated automatically
- an agent-produced summary backed by explicit inputs and a recorded commit lineage should be more trustworthy than one with only a session path
- reproducibility and inspectable inputs are part of trust, not afterthoughts

This does not mean the repo needs SLSA levels verbatim. It means trust should increasingly reflect production integrity, not just source category.

## Biba explains the current instruction-containment rule

The Biba integrity model is the integrity-side counterpart to Bell-LaPadula confidentiality rules. In simplified form, high-integrity work should not be contaminated by lower-integrity inputs.

That maps directly onto an important existing repository rule:

- low-trust knowledge may inform
- it should not directly instruct protected updates without stronger validation

This matters because it gives the trust policy a formal grounding. The rule is not arbitrary caution. It is an integrity-boundary design choice.

## Trust propagation is a real open question

P2P trust systems such as EigenTrust show that trust is often transitive only under explicit policy. That matters here because files inherit some of their meaning from the sessions and tools that produced them.

Useful questions for this repo are:

- should a file's trust depend partly on the integrity of the session that created it
- should reviewed knowledge files record who reviewed them and against what inputs
- should later correction of a session retroactively flag its derivative files for review

The current model does not yet encode that lineage strongly enough.

## Practical provenance fields that would actually help

The repository does not need a full ontology file to benefit from this research. A few concrete additions would materially improve provenance quality:

- `origin_commit` or `verified_at_commit` for content-addressed lineage
- `producer` or `produced_by` to distinguish user, agent, or tool pipeline
- optional `inputs` or `related_sources` for the artifacts consulted
- `verified_by` when trust is promoted through explicit human review

These additions would make provenance less narrative and more queryable.

## Relevance to agent-memory-seed

This research sharpens several active build plans:

- session-recording and governed write tools should capture stronger provenance than a path-only `origin_session` when possible
- worktree and freshness tooling should prefer commit-anchored provenance where the source material is a codebase
- trust rules should continue to prevent low-trust content from directly driving protected updates without a semantic gate
- schema-versioning work should treat provenance fields as part of the stable contract, not optional prose-level decoration

The architectural takeaway is that the repo's trust model is already directionally correct. What it lacks is a more explicit account of activities, agents, and content-addressed lineage.

## Sources

- W3C PROV-O documentation
- SLSA framework materials
- Integrity-model literature on Biba and related information-flow systems
