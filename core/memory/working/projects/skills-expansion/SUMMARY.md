---
active_plans: 3
cognitive_mode: planning
created: '2026-04-08'
current_focus: Gitignore-deployment-modes workstream — deployment-mode semantics and
  trust-aware defaults are the active plan focus; multi-agent distribution remains
  queued behind deployment-mode tooling.
last_activity: '2026-04-15'
open_questions: 5
origin_session: memory/activity/2026/04/08/chat-001
plans: 6
source: agent-generated
status: active
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

Execution note (2026-04-15): the original roadmap had `lifecycle-cli-decomposition` ahead of both distribution-focused tracks. That implementation has landed and is now formally closed out. The current active plan selection is therefore `gitignore-deployment-modes`, whose deployment contract now informs `multi-agent-distribution`.

1. **hook-trigger-metadata** — Complete. Trigger router landed with `memory_skill_route`, explicit frontmatter/manifest precedence, and query-driven catalog fallback for triggerless skills.
2. **skill-manifest-and-versioning** — Complete.
3. **multi-source-resolution** — Complete. Source parsing rules, `SkillResolver`, `memory_skill_install`, and `skill_install_frozen.py` landed with focused resolver/install/frozen tests.
4. **lifecycle-cli-decomposition** — Completed. The decomposed lifecycle surface (`memory_skill_list`, add/remove flows, sync support, and the lifecycle spec) is implemented and the plan metadata now matches that shipped state.
5. **gitignore-deployment-modes** — Active current focus. Deployment-mode semantics and trust-aware defaults are now the selected plan because they define the checked-vs-gitignored contract that later install, sync, and distribution work must obey.
6. **multi-agent-distribution** — Active but queued behind deployment-mode follow-through. The target/distribution spec is now drafted, but implementation should proceed after deployment-mode tooling is aligned so adapters build on settled local-install semantics.