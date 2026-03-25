# Changelog

This file records how the memory system's own structure, rules, and governance have changed over time. It is not a log of content changes (what the user said or learned) but of **system changes** (how memory is organized, stored, retrieved, and curated).

Each entry should explain not just what changed, but **why** — so that future agents can understand the evolutionary trajectory of this system and make informed decisions about further modifications.

## Format

```
## [YYYY-MM-DD] Brief title

**Changed:** What was modified, added, or removed.
**Reasoning:** Why this change was made — what problem it solves or what improvement it enables.
**Approved by:** "user" if explicitly approved, "agent (pending review)" if auto-applied and awaiting confirmation.
```

---

## Records

## [2026-03-24] Markdown section-link support in browser views

**Changed:** Expanded the shared browser markdown renderer in `HUMANS/views/engram-utils.js` to generate stable heading IDs, support same-document section links like `#heading`, and preserve cross-document anchors like `other.md#heading` through the internal cross-reference callback. Updated `knowledge.html` and `docs.html` so cross-reference navigation can open a target document and scroll to the requested section. Updated `graph.js` and its JS tests so file-level reference extraction accepts `.md#section` links without dropping the underlying document edge.

**Reasoning:** The shared renderer only recognized bare `.md` document links. As soon as a markdown link included a fragment, the renderer either treated it as a generic external URL or left it inert, which meant section links inside docs and knowledge files could not be followed. Adding anchor-aware parsing at the shared utility layer fixes the behavior consistently across the browser views and keeps the graph/reference tooling aligned with the new link format.

**Approved by:** agent (pending review)

## [2026-03-24] Shared markdown renderer and views consolidation

**Changed:** Extracted the markdown renderer from knowledge.html into a shared `Engram.renderMarkdown()` function in `engram-utils.js`. The shared renderer is DOM-safe (no innerHTML), supports headings, bold, italic, inline code, links, fenced code blocks, tables, nested lists, blockquotes, horizontal rules, and KaTeX math (display blocks and inline). It accepts an optional `onXrefClick` callback for cross-reference navigation. Replaced the 4 separate markdown renderers (knowledge.html, projects.html, skills.html, users.html) with calls to the shared version. Eliminated the unsafe innerHTML-based regex renderers in skills.html and users.html. Added KaTeX CDN (v0.16.21 with SRI integrity) to all HTML `<head>` sections (previously only knowledge.html). Moved `.math-display` CSS to `engram-shared.css`. Updated HUMANS/README.md to document skills.html, users.html, graph overlay, and KaTeX. Updated QUICKSTART.md to list all five browser views.

**Reasoning:** The four independent markdown renderers had diverged in quality and feature coverage — knowledge.html had full math support and DOM-safe construction, projects.html lacked math, and skills/users.html used regex+innerHTML which is an XSS risk even with escapeHtml pre-processing. Consolidating to a single shared renderer ensures consistent rendering quality, eliminates the innerHTML security concern for markdown content, and enables KaTeX math rendering across all views.

**Approved by:** agent (pending review)

## [2026-03-23] Views styling polish, design tokens, and documentation

**Changed:** Introduced CSS custom properties (`:root` design tokens) in `engram-shared.css` for the full color palette, border radii, shadow tokens, and monospace font stack — replacing ~60 hardcoded hex values scattered across four HTML files. Added subtle box-shadows to all card/panel components (`--shadow-card` resting, `--shadow-hover` on interactive lift). Fixed inconsistent inline-code styling: removed the pink `color: #e11d48` in knowledge.html, unified code background to `--color-code-bg` across all pages, added shared `code` rule with monospace font stack. Added 🧠 SVG favicon to all four HTML pages. Added "View all →" link to the Knowledge Base panel header in dashboard.html (was missing — projects panel already had one). Expanded `HUMANS/README.md` from a 2-line stub to a full file inventory, architecture overview, and navigation diagram for the views. Updated `HUMANS/docs/QUICKSTART.md` to mention knowledge and project viewers.

**Reasoning:** The four viewer pages had diverged in styling conventions — hardcoded colors, inconsistent code block treatment (knowledge used pink text, projects used a different background, dashboard had yet another), and no shared shadow/depth system. CSS custom properties establish a single source of truth that makes future theming (e.g. dark mode) trivial. The documentation gap meant neither humans nor agents knew the views existed or how they related to each other.

**Approved by:** agent (pending review)

## [2026-03-23] Projects dashboard and knowledge cross-reference navigation

**Changed:** Added `HUMANS/views/projects.html` — standalone project viewer with card-based list and full detail view (metadata bar, focus callout, collapsible question cards, YAML plan timeline with phase indicators, inline notes viewer). Added click-through navigation from the dashboard projects panel to projects.html. Added cross-reference navigation to knowledge.html: clickable `related:` frontmatter entries, inline markdown links to other knowledge files, and backtick file references. Updated dashboard.html with "View all →" link in the projects panel header and clickable project rows.

**Reasoning:** The dashboard provided a summary of projects and knowledge but no way to drill into detail. The projects viewer enables browsing the full project tree (questions, plans, notes) without needing an agent session. Cross-reference navigation in the knowledge viewer surfaces connections between knowledge files that were previously invisible to users.

**Approved by:** agent (pending review)

## [2026-03-23] Browser dashboard for memory repo

**Changed:** Added `HUMANS/views/dashboard.html` — a read-only browser-based dashboard that uses the File System Access API to display the state of a local memory repository. Panels: User Portrait, System Health (session/knowledge/skill/project counts, ACCESS entry stats, maturity stage), Active Projects, Recent Activity, Knowledge Base domain map, Scratchpad, and Skills. Also added a dashboard link to the setup wizard's output step so users discover it after onboarding.

**Reasoning:** Users had no way to get a quick visual overview of their memory system outside of an agent session. The dashboard extends the existing setup.html browser-only pattern (no server, no data leaves the machine) and reuses its design system for visual consistency.

## [2026-03-23] Onboarding skill refinements from validation

**Changed:** Applied three refinements to `core/memory/skills/onboarding.md` based on persona dry-run validation: (1) Phase A now includes a language-calibration note so agents adapt "repository" to the user's technical level; (2) Phase B pacing guidance now includes two concrete transition signals (user has a tangible artifact/decision, or agent has observed 4+ audit categories); (3) Discovery audit section now notes that categories should be interpreted for the user's domain with concrete translation examples. Also expanded the seed-task fallback list with a non-technical option ("organizing a project").

**Reasoning:** Validation across developer, researcher, and non-technical personas found the flow worked well for developers but had friction points for less technical users: jargon in the warm start, no concrete pacing heuristics for open-ended tasks, and software-centric audit categories.

**Approved by:** Alex

## [2026-03-22] Governance consolidation Phase 3 and maturity roadmap

**Changed:** Split `curation-policy.md` into three focused files: `curation-policy.md` (hygiene, decay, promotion rules), `content-boundaries.md` (trust-weighted retrieval and instruction containment), and `security-signals.md` (temporal decay, anomaly detection, drift monitoring, governance feedback, and periodic review orchestration). Added `security-signals.md` to the periodic review manifest in `INIT.md` and `agent-bootstrap.toml`; added `content-boundaries.md` to on-demand guidance in `INIT.md`. Updated cross-references across 13 files. Replaced the completed consolidation roadmap with a forward-looking `maturity-roadmap.md` tied to system maturity stages.

**Reasoning:** The original `curation-policy.md` had grown into a monolithic document covering three distinct concerns. Splitting reduces per-load token cost and improves maintainability. The consolidation roadmap's phases were all complete, so it was replaced with a maturity roadmap that maps future governance improvements to system maturity triggers (Calibration, periodic review count, MCP enforcement, Consolidation stage).

**Approved by:** Alex

## [2026-03-22] Legacy onboarding fallback and validator realignment

**Changed:** Archived the pre-redesign interview-style onboarding flow as `core/memory/skills/_archive/onboarding-v1.md` and added an archived-fallback reference in `core/memory/skills/SUMMARY.md`. Realigned the validator, session-start guidance, setup prompt-copy text, and Quickstart copy with the repo's current `core/memory/HOME.md`-based returning-session contract.

**Reasoning:** The collaborative onboarding redesign replaced the old intake flow, but the legacy procedure still needed an explicit fallback path. At the same time, the validator and setup guidance were still enforcing the older `projects/SUMMARY.md` startup contract, which had diverged from the architecture docs and machine bootstrap manifest. This restores consistency across runtime docs, tooling, and fallback onboarding behavior.

**Approved by:** Alex

## [2026-03-22] Collaborative onboarding redesign

**Changed:** Rewrote `core/memory/skills/onboarding.md` from an interview-style intake into a four-phase collaborative first-session flow centered on a seed task, inline capability demonstrations, post-hoc discovery audit, explicit profile confirmation, and the existing read-only export path. Updated `core/governance/first-run.md` and `core/memory/skills/SUMMARY.md` to describe the new onboarding behavior.

**Reasoning:** The previous flow preserved governance well but taught the wrong relationship model: the agent asked questions and the user filled out a profile. The redesign keeps the same safety invariants while improving user-friendliness through real collaboration, preserving consistency with existing export and archival mechanisms, and maintaining context efficiency by keeping the procedure in a single concise skill file.

**Approved by:** Alex

## [2026-03-22] Framework consistency review and README refactor

**Changed:** README slimmed from 434 to 268 lines — moved session reflection format to curation-policy.md, git publication model and MCP revert semantics to update-guidelines.md, compressed bootstrap sequence to routing pointers. Fixed INIT.md Automation path (`core/memory/working/HOME.md` → `core/memory/HOME.md`) and dangling arrow in Compact returning manifest. Aligned agent-bootstrap.toml with INIT.md by adding HOME.md to all session modes. Fixed HOME.md namespace list (`projects/OUT/` → `projects/`). Created missing `core/memory/working/projects/ACCESS.jsonl`. Added cross-reference comments between INIT.md and agent-bootstrap.toml.

**Reasoning:** Preparing for test users. README was doing too many jobs (architecture + detailed spec) and inflating first-run token cost. INIT.md and agent-bootstrap.toml had diverged after HOME.md was introduced, creating a split-brain loading manifest. Several path references from the recent reorganization were stale.

**Approved by:** Alex

---

## Prime Example

This is the actual first changelog entry, recorded by Claude Opus 4.6 at system creation. _Note: folder names below refer to the original directory structure, later reorganized under `core/memory/` (e.g. `identity/` → `core/memory/users/`, `chats/` → `core/memory/activity/`)._

## [2026-03-15] Initial system creation

**Changed:** Repository initialized with base template. Folders created for `identity/`, `knowledge/`, `skills/`, `chats/`, and `meta/`. Core protocols established in README.md including access-tracking via ACCESS.jsonl, progressive summary compression, bootstrap sequence, and update governance.

**Reasoning:** Starting point for a persistent, version-controlled Engram memory system. The template is intentionally minimal — it provides structure and protocols but almost no content, so that all personalization emerges from actual user interaction rather than assumptions.

**Approved by:** Alex
