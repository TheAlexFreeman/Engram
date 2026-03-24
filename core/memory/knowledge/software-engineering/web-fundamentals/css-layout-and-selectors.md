---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [css, flexbox, grid, selectors, specificity, responsive, layout]
related:
  - html-semantics-accessibility.md
  - browser-dom-events.md
  - ../react/chakra-ui-3-styling-system.md
  - ../react/chakra-ui-3-react-frontend-patterns.md
---

# CSS Layout and Selectors

Core CSS mechanics that Chakra UI's styling system abstracts over. Understanding the box model, Flexbox, Grid, specificity, and cascade helps debug layout issues that abstractions can't hide, and informs when to drop to raw CSS.

## 1. Box Model

Every element is a rectangular box:

```
┌────────────────── margin ──────────────────┐
│  ┌──────────── border ──────────────────┐  │
│  │  ┌──────── padding ───────────────┐  │  │
│  │  │                                │  │  │
│  │  │        content box             │  │  │
│  │  │    (width × height)            │  │  │
│  │  │                                │  │  │
│  │  └────────────────────────────────┘  │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

### `box-sizing`

```css
/* content-box (default): width = content only */
.element { width: 200px; padding: 20px; border: 1px solid; }
/* Total rendered width: 200 + 40 + 2 = 242px */

/* border-box: width = content + padding + border */
.element { box-sizing: border-box; width: 200px; padding: 20px; border: 1px solid; }
/* Total rendered width: 200px (content shrinks to 158px) */
```

Universal reset (standard practice):
```css
*, *::before, *::after {
  box-sizing: border-box;
}
```

### Margin Collapse

Vertical margins between block elements **collapse** — the larger margin wins, they don't add:

```css
.a { margin-bottom: 20px; }
.b { margin-top: 30px; }
/* Gap between .a and .b = 30px (not 50px) */
```

Margin collapse does NOT happen inside Flexbox or Grid containers — margins always add. This is one reason modern layouts feel more predictable.

## 2. Flexbox

One-dimensional layout (row OR column):

```css
.container {
  display: flex;
  flex-direction: row;       /* row | column | row-reverse | column-reverse */
  justify-content: center;   /* main axis alignment */
  align-items: stretch;      /* cross axis alignment */
  flex-wrap: wrap;            /* allow wrapping */
  gap: 16px;                 /* spacing between items */
}

.item {
  flex: 1;                   /* shorthand: flex-grow flex-shrink flex-basis */
  /* flex: 1 = flex: 1 1 0%  → grow evenly, shrink, start from 0 */
  /* flex: auto = flex: 1 1 auto  → grow/shrink based on content size */
  /* flex: none = flex: 0 0 auto  → rigid, no grow/shrink */
}
```

### Common Flexbox Patterns

```css
/* Centering (horizontal + vertical) */
.center {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* Header: logo left, nav right */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Sticky footer (footer at bottom even with short content) */
body {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
main { flex: 1; }  /* main grows to fill available space */

/* Equal-width columns */
.columns { display: flex; gap: 16px; }
.columns > * { flex: 1; }
```

### Flexbox Axis Mental Model

```
flex-direction: row
├── Main axis: →  (justify-content)
└── Cross axis: ↓  (align-items / align-self)

flex-direction: column
├── Main axis: ↓  (justify-content)
└── Cross axis: →  (align-items / align-self)
```

## 3. CSS Grid

Two-dimensional layout (rows AND columns simultaneously):

```css
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);    /* 3 equal columns */
  grid-template-rows: auto 1fr auto;        /* header, content, footer */
  gap: 16px;
}

/* Place an item in specific cells */
.sidebar {
  grid-column: 1;
  grid-row: 1 / -1;  /* span all rows */
}

.content {
  grid-column: 2 / 4;  /* span columns 2-3 */
}
```

### Grid vs Flexbox Decision

| Use Grid When | Use Flexbox When |
|---------------|------------------|
| 2D layout (rows + columns matter) | 1D layout (single row or column) |
| Page-level layout, dashboards | Component-level layout, toolbars |
| Items need to align to both axes | Items just need to distribute along one axis |
| Named grid areas for complex layouts | Simple spacing and alignment |

Both can be nested — Grid for page structure, Flexbox for component internals.

### Responsive Grid

```css
/* Auto-fill: create as many columns as fit, minimum 250px each */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}
/* No media queries needed — columns adapt to container width */
```

`auto-fill` creates empty tracks if space remains. `auto-fit` collapses empty tracks, stretching items to fill.

### Named Grid Areas

```css
.layout {
  display: grid;
  grid-template-areas:
    "header  header  header"
    "sidebar content content"
    "footer  footer  footer";
  grid-template-columns: 250px 1fr 1fr;
  grid-template-rows: auto 1fr auto;
}
.header  { grid-area: header; }
.sidebar { grid-area: sidebar; }
.content { grid-area: content; }
.footer  { grid-area: footer; }
```

## 4. Selectors and Specificity

### Specificity Calculation

Specificity is a tuple `(inline, IDs, classes, elements)`:

| Selector | Specificity | Wins Over |
|----------|-------------|-----------|
| `*` | (0,0,0,0) | Nothing |
| `p` | (0,0,0,1) | `*` |
| `.card` | (0,0,1,0) | `p` |
| `p.card` | (0,0,1,1) | `.card` |
| `#hero` | (0,1,0,0) | Any classes |
| `style="..."` | (1,0,0,0) | Any selector |
| `!important` | Trumps everything | (avoid) |

**Rules**:
- Higher specificity always wins, regardless of source order.
- Equal specificity → last one in source order wins.
- `!important` breaks the cascade — avoid except for utility overrides.

### Modern Selector Patterns

```css
/* :is() — matches any in the list, specificity = highest in list */
:is(h1, h2, h3) { margin-top: 1.5em; }

/* :where() — same as :is() but specificity is ZERO */
:where(h1, h2, h3) { margin-top: 1.5em; }  /* easily overridden */

/* :has() — parent selector (the "missing" CSS feature) */
.card:has(img) { padding: 0; }              /* card that contains an image */
.form:has(:invalid) { border-color: red; }  /* form with any invalid input */

/* :not() — negation */
input:not([type="hidden"]) { border: 1px solid #ccc; }

/* Attribute selectors */
[data-state="open"] { display: block; }     /* Chakra/Ark pattern */
a[href^="https://"] { }                      /* starts with */
a[href$=".pdf"] { }                          /* ends with */
```

### Cascade Layers (`@layer`)

```css
@layer base, components, utilities;

@layer base {
  a { color: blue; }
}
@layer components {
  .btn { color: white; }  /* wins over base regardless of specificity */
}
@layer utilities {
  .text-red { color: red !important; }  /* wins over components */
}
```

Layers establish specificity precedence independent of selector weight. Unlayered styles always beat layered styles. Chakra UI v3 uses this internally.

## 5. Positioning

| Value | Behavior | Removed from Flow? |
|-------|----------|---------------------|
| `static` | Default. No special positioning. | No |
| `relative` | Offset from normal position. Creates positioning context. | No |
| `absolute` | Positioned relative to nearest non-static ancestor. | **Yes** |
| `fixed` | Positioned relative to viewport. | **Yes** |
| `sticky` | `relative` until scroll threshold, then `fixed`. | No |

```css
/* Sticky header */
header {
  position: sticky;
  top: 0;
  z-index: 10;
}

/* Centered modal overlay */
.overlay {
  position: fixed;
  inset: 0;  /* shorthand for top/right/bottom/left: 0 */
  display: flex;
  justify-content: center;
  align-items: center;
}
```

## 6. Responsive Design

### Container Queries (Modern)

```css
/* Parent defines a containment context */
.card-wrapper { container-type: inline-size; }

/* Child responds to parent's size, not viewport */
@container (min-width: 400px) {
  .card { flex-direction: row; }
}
```

Container queries let components adapt to their available space rather than the viewport. Essential for reusable components in different layout contexts.

### Media Queries (Traditional)

```css
/* Mobile-first: base styles for small screens, then enhance */
.grid { display: flex; flex-direction: column; }

@media (min-width: 768px) {
  .grid { flex-direction: row; }
}

/* Prefer prefers-* for user preferences */
@media (prefers-color-scheme: dark) { ... }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
@media (prefers-contrast: more) { ... }
```

### Logical Properties

```css
/* Physical (LTR-only) */
margin-left: 16px;
padding-right: 16px;
border-left: 1px solid;

/* Logical (adapts to LTR/RTL automatically) */
margin-inline-start: 16px;
padding-inline-end: 16px;
border-inline-start: 1px solid;

/* Block direction (vertical in horizontal writing) */
margin-block-start: 16px;  /* like margin-top */
padding-block: 16px 24px;  /* top and bottom */
```

## 7. Modern CSS Features

```css
/* Native nesting */
.card {
  padding: 16px;

  & .title { font-weight: bold; }
  &:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }

  @media (min-width: 768px) {
    padding: 24px;
  }
}

/* Custom properties (CSS variables) */
:root {
  --color-primary: #3182ce;
  --spacing-4: 1rem;
}
.button {
  background: var(--color-primary);
  padding: var(--spacing-4);
}
/* Variables cascade and can be overridden per-element */
.dark { --color-primary: #63b3ed; }

/* clamp() — responsive sizing without media queries */
font-size: clamp(1rem, 2.5vw, 2rem);  /* min, preferred, max */
width: clamp(300px, 50%, 800px);
```

**Chakra UI relationship**: Chakra's `createSystem({ theme })` generates CSS custom properties for tokens. Understanding CSS variables and how they cascade helps debug theme issues and create custom overrides.

## Sources

- MDN CSS Layout: https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout
- CSS Tricks — Complete Guide to Flexbox: https://css-tricks.com/snippets/css/a-guide-to-flexbox/
- CSS Tricks — Complete Guide to Grid: https://css-tricks.com/snippets/css/complete-guide-grid/
- MDN CSS Specificity: https://developer.mozilla.org/en-US/docs/Web/CSS/Specificity
- MDN Container Queries: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries
