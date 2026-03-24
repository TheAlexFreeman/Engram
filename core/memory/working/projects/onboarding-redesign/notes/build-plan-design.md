---
source: agent-generated
origin_session: manual
created: 2026-03-20
trust: medium
type: design-note
---

# Collaborative Onboarding Redesign Notes

The onboarding redesign shifts the first-run experience from a scripted intake
interview to a collaborative seed-task session. The design goal is to let the
user experience memory, trust governance, and cross-session continuity through
real work instead of abstract explanation.

The plan is organized around four phases:

1. Warm start and seed-task discovery.
2. Collaborative work that surfaces profile details organically.
3. Reflection, profile confirmation, and tailored capability recap.
4. Forward bridge into the next session or project plan.

Risks called out during design remain relevant for final validation:

- The seed task can consume the whole session unless the agent explicitly
  reserves time for reflection.
- Non-technical users may need help choosing a seed task.
- Capability demonstrations should emerge naturally rather than interrupting
  flow with abstract system explanations.

Success still depends on two simultaneous outcomes: the user leaves session one
with something genuinely useful, and the system captures a confirmed durable
profile with enough fidelity to improve later sessions.

---

# Validation Findings (2026-03-23)

Dry-run of the onboarding skill across three personas: software developer,
academic researcher, and non-technical user (project manager). Each scenario
walked the full Phase A → D flow, checking the skill text, first-run.md
routing, starter templates, read-only export path, and governance gates.

## Developer persona

**Scenario:** Backend engineer using the `software-developer` starter template,
arrives with a concrete task ("stuck on rate limiting in FastAPI").

| Phase | Verdict | Notes |
|---|---|---|
| A. Warm start | Pass | Template acknowledgment path works. Developer jargon ("repository") is native to this user. Quick pivot to seed task is natural. |
| B. Seed task | Pass | Primary sweet spot — developers bring well-defined tasks. Discovery audit categories (languages, editor, frameworks) map directly to the template's blank fields. |
| C. Reflect | Pass | Audit checklist covers all high-value categories. Template reconciliation (step 4) is clear: confirm `[template]` traits → retag `[observed]`. |
| D. Forward bridge | Pass | Scratchpad offer and project suggestion land naturally for this persona. |

**Issues:** None blocking. This is the best-fit persona.

## Researcher persona

**Scenario:** PhD student using the `researcher` starter template, arrives
wanting help with a literature survey on attention mechanisms.

| Phase | Verdict | Notes |
|---|---|---|
| A. Warm start | Soft pass | "Persistent memory in this repository" may need softening for researchers less familiar with git/repo concepts. The agent should calibrate language to the user's technical level. |
| B. Seed task | Caution | Literature surveys are open-ended. The pacing warning ("watch pacing — if the seed task could consume the entire session, transition once the user has received real value") is the right safeguard, but the skill does not give concrete transition signals. An agent could struggle to judge when "enough value" has been delivered on a reading-heavy task. |
| C. Reflect | Pass | Discovery audit works, though "Editor, IDE, and recurring tools" may surface reference managers and writing tools instead of code editors — the category list adapts fine if the agent reads it broadly. |
| D. Forward bridge | Pass | Suggesting the survey as a tracked project is natural. |

**Issues found:**
1. **Pacing transition signals** — The skill warns about pacing but gives no heuristics for when to transition (e.g., "after the user has a concrete artifact or decision, even if the larger task is unfinished"). Recommend adding 1–2 transition heuristics.
2. **Warm start language** — "Repository" is developer jargon. Recommend the skill note that the opening should adapt to the user's technical vocabulary (e.g., "I keep notes in a shared workspace" for non-developers).
3. **Researcher template missing `## Codebase context`** — The `software-developer` and `project-manager` templates both include this section; `researcher` does not. May be intentional (researchers may not need it) but worth confirming for consistency.

## Non-technical persona (project manager)

**Scenario:** Marketing project manager using the `project-manager` starter
template, arrives wanting to build a campaign timeline.

| Phase | Verdict | Notes |
|---|---|---|
| A. Warm start | Caution | "Persistent memory in this repository" is opaque for non-technical users. Same language-calibration issue as researcher, but more acute — a PM may not know what a repository is. |
| B. Seed task | Pass with note | The seed-task fallback ("researching a topic, sketching a plan, or reviewing a draft") covers this persona well. Timeline-building is a natural fit. Discovery categories need broad interpretation: "languages/frameworks" → "tools and platforms," "editor/IDE" → "productivity tools." |
| C. Reflect | Pass | Profile proposal and confirmation gate work identically. Trust-tier language ("starts unverified until you confirm it") is clear enough for non-technical users when delivered conversationally. |
| D. Forward bridge | Soft pass | "Scratchpad" is a mildly technical term. The agent should say "notes space" or similar when addressing non-technical users. |

**Issues found:**
1. **Warm start jargon** (same as researcher, more severe). Concrete recommendation: add a parenthetical in Phase A guidance: _"Adapt the opening to the user's technical level — e.g., say 'I keep notes in a shared workspace' instead of 'persistent memory in this repository' for non-technical users."_
2. **Discovery audit interpretation** — The checklist categories are phrased for technical users. Adding a note that categories should be interpreted broadly for the user's domain would reduce the risk of an agent asking a PM about their "primary languages and frameworks."
3. **Seed-task fallback adequacy** — The current fallback options are good but skew slightly technical. Adding an option like "organizing a project plan" or "drafting a stakeholder update" would improve coverage for non-technical users.

## Cross-cutting findings

### What works well

- **Confirmation gate:** The "proposal → confirmation → write" discipline is clear and consistently enforced across all phases and personas.
- **Template reconciliation:** Phase C step 4 handles starter templates cleanly — confirm, retag, revise, or remove.
- **Read-only export path:** The handoff to the export template format when write access is unavailable is well-documented and consistent with `HUMANS/tooling/onboard-export-template.md`.
- **Fallback path:** The archived v1 flow provides a clear escape hatch for constrained platforms or users who prefer structured intake.
- **Quality criteria and anti-patterns:** Both sections are specific and actionable. The anti-pattern list directly addresses the risks identified during design.

### Recommended improvements

These are non-blocking refinements that would strengthen the flow for non-primary personas:

1. **Language calibration note in Phase A.** Add guidance for the agent to adapt "repository" and system-level language to the user's technical context. One sentence in the warm-start instructions would suffice.
2. **Pacing transition heuristics in Phase B.** Add 1–2 concrete signals for when to transition out of the seed task (e.g., "the user has a concrete artifact, decision, or next step — even if the larger task is incomplete").
3. **Discovery audit breadth note.** Add a short note after the audit checklist that categories should be interpreted for the user's domain, not literally as software-engineering terms.
4. **Seed-task fallback expansion.** Add one non-technical fallback option (e.g., "organizing a project plan") alongside the existing suggestions.

### Peripheral issues found during validation

- **`users/SUMMARY.md` typo:** Line 28 has `PFOFILE.md` — should be `PROFILE.md`.
- **`questions.md` discrepancy:** Project SUMMARY frontmatter says `open_questions: 5` but `questions.md` body says "None yet."
