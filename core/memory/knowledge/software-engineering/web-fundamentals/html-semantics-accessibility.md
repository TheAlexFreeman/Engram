---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [html, semantics, accessibility, a11y, aria, forms, seo]
related:
  - browser-dom-events.md
  - css-layout-and-selectors.md
  - cors-in-depth.md
  - ../react/react-error-boundaries-suspense.md
  - ../react/chakra-ui-3-overview.md
---

# HTML Semantics and Accessibility

Semantic HTML is the cheapest accessibility and SEO investment. Correct element choice provides keyboard navigation, screen reader support, and search engine understanding with zero JavaScript. This file covers the elements that matter, ARIA as a supplement (not replacement), and form accessibility patterns relevant to a React + Chakra UI stack.

## 1. Document Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page Title — App Name</title>
  <meta name="description" content="Concise page description for search engines">
  <link rel="canonical" href="https://example.com/page">
</head>
<body>
  <header>       <!-- site banner, logo, nav -->
    <nav aria-label="Main">
      <ul> <li><a href="/">Home</a></li> ... </ul>
    </nav>
  </header>
  <main>          <!-- primary content, one per page -->
    <article>     <!-- self-contained content (blog post, product card) -->
      <h1>...</h1>
      <section>   <!-- thematic grouping within article -->
        <h2>...</h2>
      </section>
    </article>
    <aside>       <!-- tangentially related (sidebar, related links) -->
    </aside>
  </main>
  <footer>        <!-- site footer, copyright, legal links -->
  </footer>
</body>
</html>
```

### Landmark Elements → ARIA Roles

| Element | Implicit ARIA Role | Screen Reader Announces |
|---------|-------------------|------------------------|
| `<header>` | `banner` (if top-level) | "Banner" |
| `<nav>` | `navigation` | "Navigation" |
| `<main>` | `main` | "Main" |
| `<aside>` | `complementary` | "Complementary" |
| `<footer>` | `contentinfo` (if top-level) | "Content information" |
| `<section>` | `region` (if labelled) | "Region: [label]" |
| `<form>` | `form` (if labelled) | "Form: [label]" |

**Rule**: Use the semantic element instead of `<div role="navigation">`. Only use `role` when no suitable HTML element exists.

## 2. Heading Hierarchy

```html
<!-- CORRECT — one h1, logical nesting -->
<h1>Product Catalog</h1>
  <h2>Electronics</h2>
    <h3>Laptops</h3>
    <h3>Phones</h3>
  <h2>Clothing</h2>

<!-- WRONG — skipped levels, multiple h1s -->
<h1>Catalog</h1>
<h1>Electronics</h1>    <!-- second h1 -->
  <h4>Laptops</h4>      <!-- skipped h2, h3 -->
```

**Rules**:
- One `<h1>` per page (the page title).
- Don't skip levels — go h1 → h2 → h3, not h1 → h3.
- Headings create an outline that screen reader users navigate via shortcut keys.

**SPA complication**: In a React SPA, the "page" changes without a full reload. Update `document.title` on route changes (TanStack Router does this via route `meta`). Manage focus — move it to the new page's `<h1>` or `<main>` on navigation.

## 3. Interactive Elements — Built-in Accessibility

### Buttons vs Links

| Element | Purpose | Keyboard | Behavior |
|---------|---------|----------|----------|
| `<button>` | Triggers an *action* | Enter, Space | No navigation |
| `<a href="...">` | Navigates to a *destination* | Enter | Navigates (right-click → open in new tab) |

```html
<!-- CORRECT -->
<button onClick={handleDelete}>Delete</button>
<a href="/orders/42">View Order #42</a>

<!-- WRONG — div/span with click handler -->
<div onClick={handleDelete} className="button">Delete</div>
<!-- Not keyboard-focusable, no role, no Enter/Space handling -->
```

**If you must use a non-semantic element** (rare), you need ALL of:
- `role="button"`
- `tabindex="0"` (makes it focusable)
- `onKeyDown` handler for Enter and Space
- Cursor styling

This is why semantic elements are always preferred — they provide all of this for free.

### Form Controls

```html
<!-- Every input MUST have a label -->
<label for="email">Email address</label>
<input type="email" id="email" name="email"
       required
       aria-describedby="email-help"
       autocomplete="email">
<p id="email-help">We'll never share your email.</p>

<!-- Grouped radio buttons -->
<fieldset>
  <legend>Shipping method</legend>
  <label><input type="radio" name="shipping" value="standard"> Standard</label>
  <label><input type="radio" name="shipping" value="express"> Express</label>
</fieldset>
```

**Critical rules**:
- Every `<input>` needs a visible `<label>` with `for`/`id` linking. Clicking the label focuses the input.
- Use `<fieldset>` + `<legend>` for radio/checkbox groups. `<fieldset>` creates a logical grouping for screen readers.
- Use native `type` attributes: `email`, `tel`, `url`, `number`, `date`. Mobile keyboards adapt. Browsers validate.
- `autocomplete` attributes help password managers and autofill.

### Input Types That Matter

| Type | Mobile Keyboard | Built-in Validation |
|------|-----------------|---------------------|
| `email` | @ key prominent | Requires `@` and domain |
| `tel` | Numeric keypad | None (format varies) |
| `url` | `.com` key, `/` | Requires protocol |
| `number` | Numeric with +/- | Min, max, step |
| `date` | Native date picker | Valid date format |
| `password` | Hide characters | None (use `minlength`) |
| `search` | Search key, × clear | None |

## 4. ARIA — When and How

ARIA (Accessible Rich Internet Applications) supplements HTML semantics for custom widgets. **First rule of ARIA**: don't use ARIA if a native HTML element does the job.

### Common ARIA Patterns

```html
<!-- Live region — announce dynamic content updates -->
<div aria-live="polite" aria-atomic="true">
  3 items in cart   <!-- screen reader announces when this text changes -->
</div>

<!-- Current page indicator in navigation -->
<nav>
  <a href="/" aria-current="page">Home</a>
  <a href="/about">About</a>
</nav>

<!-- Expandable section -->
<button aria-expanded="false" aria-controls="details-panel">
  Show Details
</button>
<div id="details-panel" hidden>...</div>

<!-- Loading state -->
<div aria-busy="true" aria-live="polite">Loading orders...</div>

<!-- Error announcement -->
<input aria-invalid="true" aria-errormessage="name-error">
<p id="name-error" role="alert">Name is required</p>
```

### ARIA Live Regions

| Value | Behavior |
|-------|----------|
| `polite` | Announces when the screen reader is idle (use for most updates) |
| `assertive` | Interrupts immediately (use for errors, urgent alerts only) |
| `off` | No announcement |

**`aria-atomic`**: When `true`, the entire live region is re-read on any change. When `false` (default), only the changed node is read. Set `true` for short status messages, `false` for chat logs or lists.

### ARIA Roles for Custom Widgets

| Widget | Role | Required Properties |
|--------|------|---------------------|
| Tab interface | `tablist`, `tab`, `tabpanel` | `aria-selected`, `aria-controls` |
| Modal dialog | `dialog` | `aria-modal="true"`, `aria-labelledby` |
| Combobox (autocomplete) | `combobox`, `listbox`, `option` | `aria-expanded`, `aria-activedescendant` |
| Accordion | `heading` + `button` | `aria-expanded`, `aria-controls` |
| Toast notification | `status` or `alert` | (live region, announced automatically) |

**Chakra UI context**: Chakra (via Ark UI) implements these ARIA patterns in its component primitives. The `Dialog`, `Tabs`, `Combobox`, and `Toast` components handle roles, focus management, and keyboard interaction. Understanding the underlying ARIA contract helps debug when behavior seems wrong.

## 5. Focus Management

### Tab Order

```html
<!-- Natural tab order follows DOM order. Use tabindex sparingly: -->
<div tabindex="0">Focusable (added to tab order at its DOM position)</div>
<div tabindex="-1">Focusable via JS only (not in tab order)</div>
<!-- NEVER use tabindex > 0 — it breaks natural tab order globally -->
```

### Focus Trapping (Modals)

When a modal is open, Tab should cycle within it — not escape to the page behind:

```javascript
// Trap focus in a dialog
dialog.addEventListener('keydown', (e) => {
  if (e.key !== 'Tab') return;
  const focusable = dialog.querySelectorAll(
    'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (e.shiftKey && document.activeElement === first) {
    last.focus(); e.preventDefault();
  } else if (!e.shiftKey && document.activeElement === last) {
    first.focus(); e.preventDefault();
  }
});
```

The `<dialog>` element with `showModal()` handles focus trapping natively. Chakra's `Dialog` component also manages this.

### Skip Links

```html
<body>
  <a href="#main-content" class="skip-link">Skip to main content</a>
  <header>...</header>
  <main id="main-content">...</main>
</body>

<style>
.skip-link {
  position: absolute;
  left: -10000px;
}
.skip-link:focus {
  left: 10px; top: 10px; /* visible when focused */
}
</style>
```

## 6. Images and Media

```html
<!-- Informative image — describe the content -->
<img src="chart.png" alt="Q1 revenue: $2.3M, up 15% from Q4">

<!-- Decorative image — empty alt -->
<img src="divider.svg" alt="">

<!-- Complex image — longer description -->
<figure>
  <img src="architecture.png" alt="System architecture diagram">
  <figcaption>Django API, Redis cache, and React SPA connected via Nginx reverse proxy</figcaption>
</figure>

<!-- SVG icons — label with aria -->
<button aria-label="Close">
  <svg aria-hidden="true">...</svg>
</button>
```

**Rules**:
- Every `<img>` must have an `alt` attribute (even if empty for decorative images).
- `alt=""` tells screen readers to skip the image entirely.
- For icon-only buttons, use `aria-label` on the button and `aria-hidden="true"` on the icon.

## 7. Testing Accessibility

| Tool | Type | Catches |
|------|------|---------|
| **axe DevTools** (browser extension) | Automated | Missing alt, color contrast, missing labels, ARIA misuse |
| **Lighthouse Accessibility** | Automated audit | Score + itemized violations |
| **Screen reader** (NVDA, VoiceOver) | Manual | Actual user experience, reading order, announcement quality |
| **Keyboard-only testing** | Manual | Tab order, focus visibility, no mouse traps |
| **eslint-plugin-jsx-a11y** | Static analysis | Missing alt, invalid ARIA in JSX |

**Automated tools catch ~30-50% of issues**. The rest require manual testing: logical reading order, meaningful link text, comprehensible form error messages, and coherent focus management.

### eslint-plugin-jsx-a11y (React)

```json
// .eslintrc or eslint.config.js
{
  "plugins": ["jsx-a11y"],
  "extends": ["plugin:jsx-a11y/recommended"]
}
```

Catches at build time: `<img>` without `alt`, `onClick` on non-interactive elements without `role`/`tabindex`, invalid ARIA attributes.

## Sources

- MDN HTML Elements: https://developer.mozilla.org/en-US/docs/Web/HTML/Element
- WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
- WebAIM: https://webaim.org/
- Deque axe Rules: https://dequeuniversity.com/rules/axe/
- MDN Accessibility: https://developer.mozilla.org/en-US/docs/Web/Accessibility
