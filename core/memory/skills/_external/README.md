# External Skill Sources

`core/memory/skills/_external/` is the human-visible staging area for notes, imported bundles, or operator-curated artifacts related to skills that originate outside the current vault.

It is not the runtime cache.

- Active installed skills still live under `core/memory/skills/{slug}/`.
- `SKILLS.yaml` remains the authoritative declaration of which external sources are in use.
- `SKILLS.lock` records the exact source string, resolved ref, and content hash for reproducible installs.
- The runtime resolver caches cloned git/github sources under `.git/engram/skill-cache/` so fetched checkouts do not pollute the tracked tree.

Use `_external/` when you want a committed, inspectable breadcrumb for shared skills or external provenance. Use the resolver cache for ephemeral fetched content.
