# Starter Profile Templates

These templates are installed by `setup/setup.sh --profile <name>` or by the `setup/setup.html` wizard. Each one pre-fills `core/memory/users/profile.md` with common traits for a given role, tagged `[template]` so the onboarding skill knows to confirm them with the user.

## Existing templates

- `software-developer.md` — Code-first, concise, technical.
- `researcher.md` — Thorough, rigorous, citation-aware.
- `project-manager.md` — Concise, actionable, stakeholder-ready.
- `writer.md` — Narrative-first, tone-conscious, revision-oriented.
- `student.md` — Curious, explanation-seeking, building foundations.
- `educator.md` — Clear, scaffolded, student-centered.
- `designer.md` — Iterative, feedback-driven, concrete over abstract.

## Creating a new template

1. Copy an existing template and rename it (use kebab-case: `data-scientist.md`).
2. Keep the frontmatter exactly as-is:
   ```yaml
   ---
   source: template
   origin_session: setup
   created: YYYY-MM-DD
   trust: medium
   ---
   ```
   `setup.sh` replaces `YYYY-MM-DD` with today's date at install time. Do not add `last_verified` here — onboarding writes that only after the user confirms the template.
3. Use `[template]` tags on every pre-filled trait. The onboarding skill walks through each `[template]` trait and asks the user to confirm, adjust, or remove it.
4. Leave fields that vary too much to guess as `_[To be filled during onboarding]_`.
5. Include a `## Customize me` section at the end explaining that traits are starting points.
6. Add the new template name to the interactive menu in `setup/setup.sh` and to the cards in `setup/setup.html`. Also update the profile validation case in `setup/setup.sh`.
