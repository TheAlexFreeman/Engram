---
name: onboarding
description: >-
  First-session user onboarding. Runs a collaborative seed-task session that
  surfaces the user's role, preferences, and working style while demonstrating
  memory and trust behavior in context.
compatibility: Requires write access for profile persistence; produces export on read-only platforms
trigger:
  event: session-start
  matcher:
    condition: first_session
  priority: 100

source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Onboarding: First-Session User Discovery

## When to use this skill

Activate this skill on the **first session only** — when no date-organized chat folders exist in `core/memory/activity/`, AND either:

1. `core/memory/users/SUMMARY.md` contains "No portrait yet" (blank-slate setup — no profile installed), OR
2. `core/memory/users/` contains a file with `source: template` in its frontmatter (a starter profile was installed by `setup.sh --profile` but has not yet been confirmed through onboarding).

If neither condition matches — a confirmed user portrait exists, or chat history is present — the system has already been onboarded. Return to `core/INIT.md` and follow its routing instead.

Before using this skill, the agent should already have been routed here from `core/INIT.md`, reviewed the relevant change-control and read-only sections of `core/governance/update-guidelines.md`, and checked write access per the first-run flow in `core/governance/first-run.md`.

## Flow

Treat onboarding as a first working session, not an intake form. The user should leave with a useful result and a confirmed profile.

### Phase A. Warm start

Open with one short paragraph: this is your first meeting, you keep persistent memory in this repository, and you want to learn by working together. Adapt this language to the user's technical level — for non-technical users, say something like "I keep notes in a shared workspace" instead of referencing repositories or memory systems.

Then ask what the user is working on, stuck on, or curious about. The answer becomes the **seed task**.

If `core/memory/users/` contains a file with `source: template`, acknowledge it briefly: "I see you started with the [role] template. Let's test that against how we work together." Do not turn template review into a separate interview. Use it as prior context while the session unfolds.

If the user does not bring a concrete task, offer a prompt such as researching a topic, sketching a plan, organizing a project, or reviewing a draft.

### Phase B. Work the seed task collaboratively

Spend most of the session here. Help with the task while silently tracking what you learn about the user.

During this phase:

1. Discover profile details through the work: role, projects, expertise, tools, style, and anti-preferences.
2. Ask direct follow-up questions only when a major category is still missing.
3. Make memory visible in context. When the user reveals something durable, say so briefly. When a correction improves future work, acknowledge that explicitly.
4. Make trust visible only when relevant. If you introduce external information or a synthesized inference, note that direct user statements can be saved at high trust while external or inferred material starts lower until confirmed.
5. Watch pacing. If the seed task could consume the entire session, transition once the user has received real value and you have enough signal for a useful portrait. Concrete transition signals: the user has a tangible artifact, a decision, or a clear next step — even if the larger task is unfinished; or you have observed enough traits across at least 4 discovery-audit categories to draft a useful portrait.

Use demonstrations as natural moments, not a script. Aim for 2 to 3 across the session. See [references/demo-menu.md](references/demo-menu.md) for the demonstration menu.

### Phase C. Reflect, fill gaps, and propose the profile

When the seed task reaches a natural pause, shift explicitly: "Before we wrap, here's what I've learned about how you work."

1. Reflect back the working portrait based on the collaboration, not just direct Q&A.
2. Audit for gaps using the [discovery audit checklist](references/discovery-audit.md). Ask only the minimum targeted questions needed to cover missing high-value categories.
3. Give a short tailored capability tour: 2 or 3 things this system can do for this user. Keep it concrete and tied to the seed task.
4. If a starter template exists, reconcile it now: confirm accurate traits, revise or remove bad ones, and retag confirmed template traits as `[observed]`.
5. Ask the open-ended capture question: _"Is there anything else you'd like me to remember going forward that would make our work more useful?"_

Then draft the proposed profile. Use the canonical frontmatter:

```yaml
---
source: user-stated
origin_session: core/memory/activity/YYYY/MM/DD/chat-001
created: YYYY-MM-DD
last_verified: YYYY-MM-DD
trust: high
---
```

Tag direct statements as `[observed]`. If something is plausible but unconfirmed, mark it `[tentative]` or ask before including it.

State clearly that writing to `core/memory/users/` is a proposed-tier change requiring explicit confirmation. Revise if needed. Write only after the user clearly approves.

If write access is unavailable, do not attempt repo writes. Produce the confirmed result in the onboarding export format from `HUMANS/tooling/onboard-export-template.md` with `session_id`, `session_date`, `## Identity Profile`, `## Session Transcript`, `## Session Summary`, and `## Session Reflection`. Use `core/memory/activity/YYYY/MM/DD/chat-001` for `session_id`.

If the user never confirms the proposed profile, do not write to `core/memory/users/`.

### Phase D. Forward bridge

End by making session two feel real:

1. Briefly say what next time will feel like: you will greet them with what you learned and can pick up open threads.
2. Offer `core/memory/working/USER.md` as a place for notes between sessions.
3. If the seed task has follow-up work, suggest tracking it as a project or plan.
4. If `core/memory/working/projects/codebase-survey/SUMMARY.md` exists and its status is `active`, mention the codebase survey as the natural first project to pick up next session. Frame it concretely: "Next time I'll start mapping [project name]'s architecture so future sessions can orient quickly."
5. Close as someone who now knows the user, not as a generic system.

## Session record

After confirmation or session close, follow the standard chat archival flow:

- Create `core/memory/activity/YYYY/MM/DD/chat-001/`.
- Write `transcript.md`, `SUMMARY.md`, and `reflection.md`.
- Append ACCESS notes for relevant files read during onboarding.
- On read-only platforms, keep the first-session transcript, summary, reflection, and confirmed profile inside the onboarding export instead of a separate deferred-action block.

## Quality criteria

- The first session produces a useful collaborative outcome **and** a usable profile.
- The profile captures **5 to 10 durable traits** with clear confidence tagging.
- The user experiences at least **2 to 3 concrete capability demonstrations** during the session.
- Communication preferences are specific enough to measurably change the next session.
- No trait is invented; ambiguous points are either confirmed or marked `[tentative]`.
- No `core/memory/users/` write occurs before explicit user confirmation.

## Anti-patterns

- **Don't interrogate.** The checklist is for audit, not for marching through fixed questions.
- **Don't explain the system abstractly when you can demonstrate it in context.** Show memory and trust with real moments from the session.
- **Don't let the seed task consume the whole onboarding.** Leave room for reflection, confirmation, and the forward bridge.
- **Don't over-collect.** A compact, durable portrait is better than a long intake dump.
- **Don't write memory optimistically.** Proposal first, confirmation second, write third.
