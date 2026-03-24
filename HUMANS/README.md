# Human-Focused Documentation

Agents generally shouldn't bother loading any files from this directory unless explicitly instructed to do so.

## Browser views (`views/`)

A collection of standalone HTML pages for browsing a local Engram memory repo in the browser. Everything runs client-side using the **File System Access API** — no server, no data leaves your machine. Requires **Chrome, Edge, Brave, or Arc**.

| File | Purpose |
|------|---------|
| `setup.html` | **Entry point.** Three-step onboarding wizard: personal context, starter profile, platform instructions. |
| `dashboard.html` | **Hub.** Seven-panel overview: User Portrait, System Health, Active Projects, Recent Activity, Knowledge Base, Scratchpad, and Skills. Links to all other views. |
| `knowledge.html` | Knowledge base explorer with domain picker, file sidebar, frontmatter metadata, markdown rendering, and cross-reference navigation between knowledge files. |
| `projects.html` | Project viewer with card-based list and detail view: metadata, focus callout, collapsible questions, YAML plan timeline with phase indicators, inline note viewer. |

### Architecture

- **`engram-shared.css`** — CSS custom properties (`:root` design tokens for colors, radius, shadows, font stacks) plus shared component styles (badges, nav-links, domain cards, placeholders, error banners).
- **`engram-utils.js`** — `window.Engram` namespace with shared utilities: File System Access helpers (`readFile`, `listDir`), IndexedDB handle persistence (`loadSavedHandle`, `saveHandle`), frontmatter/YAML/markdown-table parsers, DOM helpers.
- Each HTML page imports both shared files plus its own inline `<style>` and `<script>` blocks.
- **IndexedDB** stores the directory handle so users only pick their repo folder once (on the dashboard). All viewer pages read the same saved handle.

### Navigation

```
setup.html  →  dashboard.html  ─→  knowledge.html
                     │              projects.html
                     └──────────→  setup.html
```
