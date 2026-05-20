---
active_plans: 0
cognitive_mode: execution
created: '2026-04-08'
current_focus: The original six-workstream roadmap is now complete. Future skill-system
  changes should be opened as follow-on enhancement plans rather than continued under
  this project.
last_activity: '2026-04-15'
open_questions: 0
origin_session: memory/activity/2026/04/08/chat-001
plans: 6
source: agent-generated
status: completed
trust: medium
type: project
---

# Project: Skills Expansion

## Description
Modernize Engram's skill system by adopting lessons from the dotagents package manager architecture and the narrative-vs-formal specification framework. Six workstreams: declarative skill manifests with versioning and lockfiles, multi-source resolution (git/registry/local), lifecycle CLI decomposition, explicit hook trigger metadata, multi-agent distribution via symlinks, and gitignore deployment modes. Goal is to make Engram vaults reproducible, portable, and ready for multi-user/multi-team adoption.

## Design principles (added 2026-04-09)

From analysis of the "Personality and Narrative for AI Agents" transcript:

- **Narrative by default, formal only where determinism is load-bearing.** Skills steer via prose (the SKILL.md "character sheet"); formal mechanisms (triggers, validators, state machines) should only be introduced where non-determinism would cause real failures — checkpoints, retries, audit logs, dispatch ordering.
- **The harness is a stage manager, not a puppet master.** Engram's job is context curation (assembling the right narrative), not orchestration (directing every step). The trigger system is the right formal layer for *when* skills activate; the skill body stays narrative for *how* they guide behavior.
- **Progressive disclosure is the scaling pattern.** Skills should be cheap in summary form (a few tokens in the manifest) and load full narrative only when matched. This is the same mechanism that makes the bootstrap token budget work.
- **Evaluation is ethnographic.** Skill quality should be assessed across sessions ("does this pattern of behavior reflect the character we specified?"), not as unit tests. The sidecar transcript system provides the raw data; an eval harness is a natural next step.
- **The graduation pipeline may need to be bidirectional.** Knowledge → skills → tools is the forward path, but brittleness in formal control is a signal to relax back to narrative.

## Workstream status and execution sequence

Execution note (2026-04-15): the original roadmap had `lifecycle-cli-decomposition` ahead of both distribution-focused tracks. That implementation has landed and is now formally closed out. The deployment contract from `gitignore-deployment-modes` is now stable enough that active execution has moved to `multi-agent-distribution`, beginning with the completed `distribution-targets` specification.

1. **hook-trigger-metadata** — Complete. Trigger router landed with `memory_skill_route`, explicit frontmatter/manifest precedence, and query-driven catalog fallback for triggerless skills.
2. **skill-manifest-and-versioning** — Complete.
3. **multi-source-resolution** — Complete. Source parsing rules, `SkillResolver`, `memory_skill_install`, and `skill_install_frozen.py` landed with focused resolver/install/frozen tests.
4. **lifecycle-cli-decomposition** — Completed. The decomposed lifecycle surface (`memory_skill_list`, add/remove flows, sync support, and the lifecycle spec) is implemented and the plan metadata now matches that shipped state.
5. **gitignore-deployment-modes** — Implemented and verified. Deployment-mode spec, managed `.gitignore` reconciliation, install/sync semantics, and the fresh-clone recovery rule are in place; that stabilized contract now feeds the distribution work.
6. **multi-agent-distribution** — Completed. Built-in target ids (`engram`, `generic`, `claude`, `cursor`, `codex`) are specified, the adapter-backed distributor and CLI landed, lifecycle tools validate and persist manifest `targets`, `memory_skill_list` reports distribution health, and `memory_skill_sync` now verifies stale projections, repairs rendered outputs, and prunes obsolete target entries. Focused distributor, lifecycle, integration, and CLI tests are green.

Project closure note (2026-04-15): all six planned workstreams are complete. Any additional skills work should be scoped as a new follow-on project or a targeted maintenance plan instead of extending this closed roadmap.
