# Human-Focused Documentation

Agents generally shouldn't bother loading any files from this directory unless explicitly instructed to do so.

## Browser views (`views/`)

A collection of standalone HTML pages for browsing a local Engram memory repo in the browser. Everything runs client-side using the **File System Access API** — no server, no data leaves your machine. Requires **Chrome, Edge, Brave, or Arc**.

| File | Purpose |
|------|---------|
| `setup.html` | **Entry point.** Three-step onboarding wizard: personal context, starter profile, platform instructions. |
| `dashboard.html` | **Hub.** Seven-panel overview: User Portrait, System Health, Active Projects, Recent Activity, Knowledge Base, Scratchpad, and Skills. Links to all other views. |
| `knowledge.html` | Knowledge base explorer with domain picker, file sidebar, frontmatter metadata, markdown rendering (with KaTeX math), and cross-reference navigation. Includes a canvas-based graph overlay (`graph.js`/`graph.css`) for visualizing link structure. |
| `projects.html` | Project viewer with card-based list and detail view: metadata, focus callout, collapsible questions, YAML plan timeline with phase indicators, inline note viewer. |
| `skills.html` | Skill library browser. Lists skills from `core/memory/skills/` (active and archived) with trust badges, detail view with frontmatter metadata, and full markdown rendering. |
| `users.html` | User profile browser. Lists user directories from `core/memory/users/` with avatar cards, per-user file sidebar, detail view with frontmatter metadata, and full markdown rendering. |
| `docs.html` | **Documentation viewer.** Card-based index of all human-facing docs with sidebar reader, markdown rendering (with KaTeX), breadcrumb navigation, and deep-link support via `?doc=FILENAME` query params. |
| `traces.html` | Session trace viewer with session selector, timeline view, filter chips, and stats bar. |
| `approvals.html` | Approval queue browser with pending approvals (expiry countdowns, context, approve/reject buttons) and resolved history. |
| `index.html` | Redirect to `setup.html`. |

### Architecture

- **`engram-shared.css`** — CSS custom properties (`:root` design tokens for colors, radius, shadows, font stacks) plus shared component styles (badges, nav-links, domain cards, placeholders, error banners, KaTeX math display).
- **`engram-utils.js`** — `window.Engram` namespace with shared utilities: File System Access helpers (`readFile`, `listDir`), IndexedDB handle persistence (`loadSavedHandle`, `saveHandle`), frontmatter/YAML/markdown-table parsers, DOM helpers, and a shared DOM-safe markdown renderer (`renderMarkdown`) with KaTeX math support.
- **`graph.js` / `graph.css`** — Knowledge graph overlay for `knowledge.html`. Canvas-based force-directed graph with domain coloring, node preview, zoom, search, and network analysis tools.
- Each HTML page imports the shared files, **KaTeX** (CDN), plus its own inline `<style>` and `<script>` blocks.
- **IndexedDB** stores the directory handle so users only pick their repo folder once (on the dashboard). All viewer pages read the same saved handle.

### Navigation

```
setup.html  →  dashboard.html  ─→  knowledge.html
(index.html)         │              projects.html
                     │              skills.html
                     │              users.html
                     │              docs.html
                     │              traces.html
                     │              approvals.html
                     └──────────→  setup.html
```
