---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [dom, browser, events, rendering, react-dom, web-apis]
related:
  - javascript-core-patterns.md
  - html-semantics-accessibility.md
  - css-layout-and-selectors.md
  - ../react/react-performance.md
  - ../react/react-19-overview.md
---

# Browser, DOM, and Events

How the browser turns HTML/CSS/JS into an interactive page, and how events flow through the DOM tree. Foundation for understanding why React manages DOM updates the way it does, and where performance bottlenecks originate.

## 1. Browser Rendering Pipeline

```
HTML bytes → Parse → DOM tree
                        ↓
CSS bytes  → Parse → CSSOM tree → Render tree → Layout → Paint → Composite
                        ↑
                    JS execution (can modify DOM/CSSOM)
```

| Stage | What Happens | Expensive? |
|-------|-------------|------------|
| **Parse** | Tokenize HTML, build DOM tree. CSS parsed into CSSOM. | Fast for typical pages |
| **Script execution** | `<script>` blocks parsing (unless `async`/`defer`). JS can read/mutate DOM. | Depends on JS size |
| **Render tree** | Combines DOM + CSSOM. Excludes `display: none` elements. | Fast |
| **Layout (reflow)** | Computes geometry: position, size, and containment of every visible node. | **Expensive** — triggered by geometry changes |
| **Paint** | Fills pixels: text, colors, images, borders, shadows. | Moderate — triggered by visual changes |
| **Composite** | GPU layers assembled into final image. `transform`/`opacity` changes stay here. | **Cheap** — GPU-accelerated |

### What Triggers What

| Change Type | Triggers | Examples |
|-------------|----------|----------|
| Geometry | Layout → Paint → Composite | `width`, `height`, `margin`, `padding`, `top`, `font-size` |
| Visual only | Paint → Composite | `color`, `background`, `box-shadow`, `visibility` |
| Transform/opacity | Composite only | `transform`, `opacity` (on own layer) |

**Key insight**: Reading layout properties (`offsetWidth`, `getBoundingClientRect()`, `scrollTop`) forces the browser to flush pending layout — called **forced synchronous layout**. Interleaving reads and writes in a loop is the classic performance anti-pattern:

```javascript
// BAD — forced layout thrashing
elements.forEach(el => {
  const width = el.offsetWidth;       // forces layout
  el.style.width = (width + 10) + 'px'; // invalidates layout
});

// GOOD — batch reads, then batch writes
const widths = elements.map(el => el.offsetWidth);
elements.forEach((el, i) => {
  el.style.width = (widths[i] + 10) + 'px';
});
```

## 2. DOM Tree and Node Types

The DOM is a tree of nodes. Every node has a `nodeType`:

| Constant | Value | Example |
|----------|-------|---------|
| `ELEMENT_NODE` | 1 | `<div>`, `<p>`, `<button>` |
| `TEXT_NODE` | 3 | Text content between tags |
| `COMMENT_NODE` | 8 | `<!-- comment -->` |
| `DOCUMENT_NODE` | 9 | `document` itself |
| `DOCUMENT_FRAGMENT_NODE` | 11 | `DocumentFragment` (virtual container) |

### Traversal

```javascript
// Children
element.children          // HTMLCollection of element children (live)
element.childNodes        // NodeList including text/comment nodes (live)
element.firstElementChild // first child element
element.querySelector('.class')      // first match (static)
element.querySelectorAll('.class')   // NodeList of all matches (static)

// Siblings
element.nextElementSibling
element.previousElementSibling

// Parent
element.parentElement
element.closest('.ancestor')  // walks up the tree, returns first match
```

**Live vs static collections**: `getElementsByClassName()` and `children` return *live* collections — they update when the DOM changes. `querySelectorAll()` returns a *static* snapshot. Live collections in a mutation loop cause surprising behavior.

### Mutation

```javascript
// Create
const div = document.createElement('div');
div.textContent = 'Hello';
div.classList.add('card');

// Insert
parent.appendChild(div);                    // append as last child
parent.insertBefore(div, referenceNode);    // insert before a sibling
parent.append(div, 'text', otherEl);        // multi-insert (modern)
parent.prepend(div);                        // insert as first child

// Remove
element.remove();                           // self-remove (modern)
parent.removeChild(element);                // classic

// Replace
parent.replaceChild(newEl, oldEl);
oldEl.replaceWith(newEl);                   // modern
```

**DocumentFragment**: For inserting many elements, build them in a `DocumentFragment` first. It's a lightweight container that doesn't trigger layout until appended:

```javascript
const fragment = document.createDocumentFragment();
items.forEach(item => {
  const li = document.createElement('li');
  li.textContent = item.name;
  fragment.appendChild(li);
});
list.appendChild(fragment); // single DOM insertion
```

## 3. Event Model

### Phases

Every DOM event flows through three phases:

```
                    CAPTURE PHASE (window → target)
window → document → html → body → ... → target element
                                            │
                                        TARGET PHASE
                                            │
target element → ... → body → html → document → window
                    BUBBLE PHASE (target → window)
```

Most events bubble (click, keydown, input, submit). Some don't (focus, blur, scroll, load).

### Event Listeners

```javascript
// Modern — preferred
element.addEventListener('click', handler, { capture: false, once: false, passive: false });

// Options:
//   capture: true  → fires during capture phase
//   once: true     → removes after first invocation
//   passive: true  → promises not to call preventDefault() (perf hint for scroll/touch)
```

### Event Delegation

Instead of attaching listeners to every child, attach one to the parent and check `event.target`:

```javascript
// Instead of N listeners on N <li> elements:
document.querySelector('.todo-list').addEventListener('click', (e) => {
  const item = e.target.closest('[data-id]');
  if (item) handleClick(item.dataset.id);
});
```

**Why this matters for React**: React uses a single event listener on the root (`#root`) and implements its own synthetic event system. This is event delegation at scale — React intercepts all events at the root and dispatches to the correct component.

### Stopping Propagation

```javascript
e.stopPropagation();          // stop further handlers in current phase + remaining phases
e.stopImmediatePropagation(); // stop ALL remaining handlers, even on the same element
e.preventDefault();           // cancel the default browser action (not propagation)
```

**`preventDefault` vs `stopPropagation`**: These are orthogonal. `preventDefault()` on a form submit prevents page navigation. `stopPropagation()` prevents parent handlers from firing. You usually want one, rarely both.

## 4. Key Browser APIs

### IntersectionObserver — Visibility Detection

Fires when an element enters/exits the viewport. More efficient than scroll listeners:

```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      loadImage(entry.target);
      observer.unobserve(entry.target); // one-time observation
    }
  });
}, { threshold: 0.1, rootMargin: '200px' });

document.querySelectorAll('img[data-src]').forEach(img => observer.observe(img));
```

Use cases: lazy loading images, infinite scroll triggers, analytics visibility tracking.

### MutationObserver — DOM Change Detection

```javascript
const observer = new MutationObserver((mutations) => {
  mutations.forEach(m => console.log(m.type, m.target));
});
observer.observe(targetNode, {
  childList: true,    // direct child additions/removals
  subtree: true,      // observe all descendants
  attributes: true,   // attribute changes
  characterData: true // text content changes
});
```

### ResizeObserver — Element Size Changes

```javascript
const observer = new ResizeObserver((entries) => {
  for (const entry of entries) {
    const { width, height } = entry.contentRect;
    // respond to size change
  }
});
observer.observe(element);
```

### requestAnimationFrame — Smooth Visual Updates

```javascript
function animate() {
  // update positions/styles here — runs once per frame (~16ms at 60fps)
  element.style.transform = `translateX(${position}px)`;
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
```

Batches visual updates with the browser's paint cycle. Always preferred over `setTimeout`/`setInterval` for animations.

### requestIdleCallback — Low-Priority Work

```javascript
requestIdleCallback((deadline) => {
  while (deadline.timeRemaining() > 0 && tasks.length > 0) {
    processTask(tasks.pop());
  }
}, { timeout: 2000 }); // max wait before forced execution
```

Runs during idle periods between frames. Use for analytics, pre-fetching, or non-urgent computation.

## 5. Script Loading Strategies

```html
<!-- Blocks parsing until script downloads AND executes -->
<script src="app.js"></script>

<!-- Downloads in parallel, executes ASAP (may execute before DOM is ready) -->
<script src="analytics.js" async></script>

<!-- Downloads in parallel, executes after HTML parsing complete, in order -->
<script src="app.js" defer></script>

<!-- ES module — deferred by default, strict mode -->
<script type="module" src="app.js"></script>
```

| Attribute | Downloads During Parse? | Execution Order | Blocks Parsing? |
|-----------|------------------------|-----------------|-----------------|
| (none) | No — blocks | In document order | **Yes** |
| `async` | Yes — parallel | Whichever finishes first | Only during execution |
| `defer` | Yes — parallel | In document order | **No** |
| `type="module"` | Yes — parallel | In document order | **No** (deferred) |

**Vite output**: Vite generates `<script type="module">` tags. ES modules are deferred by default, so they don't block the initial HTML parse. The `modulepreload` link hints Vite adds tell the browser to start fetching module dependencies early.

## 6. Critical Rendering Path Optimization

| Technique | Effect |
|-----------|--------|
| Inline critical CSS | Avoids render-blocking stylesheet fetch for above-the-fold content |
| `defer` / `type="module"` scripts | Unblock HTML parsing |
| `<link rel="preload">` for fonts/images | Start downloading critical resources early |
| `<link rel="preconnect">` for API origins | Eliminate connection setup latency |
| `content-visibility: auto` (CSS) | Skip rendering of off-screen content |
| `loading="lazy"` on images/iframes | Defer loading until near viewport |
| `fetchpriority="high"` on LCP image | Hint browser to download hero image first |

See [react-performance.md](../react/react-performance.md) for React-specific rendering optimization (memoization, virtualization) that builds on these browser primitives.
