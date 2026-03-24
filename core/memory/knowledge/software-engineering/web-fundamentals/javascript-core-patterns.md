---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [javascript, async, promises, event-loop, closures, modules, es2025]
related:
  - browser-dom-events.md
  - ../react/react-19-overview.md
  - ../react/typescript-react-patterns.md
  - ../react/react-performance.md
  - web-storage-and-state.md
---

# JavaScript Core Patterns

Essential JavaScript mechanics that underpin React, Node.js (build tools), and browser APIs. Focuses on the patterns that cause real bugs and the mental models that prevent them.

## 1. The Event Loop

JavaScript is single-threaded. All I/O is asynchronous, coordinated by the event loop:

```
┌──────────────────────┐
│      Call Stack       │  ← synchronous code runs here
└─────────┬────────────┘
          │ (when stack is empty)
          ▼
┌──────────────────────┐
│   Microtask Queue    │  ← Promise callbacks, queueMicrotask, MutationObserver
└─────────┬────────────┘
          │ (drain ALL microtasks)
          ▼
┌──────────────────────┐
│   Macrotask Queue    │  ← setTimeout, setInterval, I/O, UI events
└──────────────────────┘
```

**Order**: Run all synchronous code → drain all microtasks → run one macrotask → drain all microtasks → repeat.

```javascript
console.log('1');                          // sync
setTimeout(() => console.log('2'), 0);     // macrotask
Promise.resolve().then(() => console.log('3')); // microtask
console.log('4');                          // sync
// Output: 1, 4, 3, 2
```

**Microtasks always run before the next macrotask**. A common bug: an infinite loop of microtasks (recursive `Promise.then`) starves all macrotasks — `setTimeout` callbacks, UI events, and rendering never fire.

### `queueMicrotask()` vs `setTimeout(fn, 0)`

`queueMicrotask` runs before any macrotask or rendering. `setTimeout(fn, 0)` runs in the next macrotask — after rendering and other events. Use `queueMicrotask` for completion callbacks that must run before the browser has a chance to paint.

## 2. Closures and Scope

A closure captures variables from its enclosing scope — not their *values* at capture time, but the *variables themselves*:

```javascript
function makeCounters(n) {
  const counters = [];
  for (var i = 0; i < n; i++) {
    counters.push(() => i); // all closures share the SAME `i`
  }
  return counters;
}
makeCounters(3).map(fn => fn()); // [3, 3, 3] — not [0, 1, 2]

// Fix: use `let` (block-scoped, new binding per iteration)
for (let i = 0; i < n; i++) {
  counters.push(() => i); // each closure gets its own `i`
}
```

### Stale Closures in React

The same mechanic causes stale closure bugs in React hooks:

```javascript
function Counter() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      console.log(count); // always logs 0 — closure captured initial count
    }, 1000);
    return () => clearInterval(id);
  }, []); // empty deps → effect runs once, closure never updates

  // Fix: use functional updater or add `count` to deps
  setInterval(() => setCount(prev => prev + 1), 1000); // functional: no stale closure
}
```

## 3. `this` Binding

`this` in JavaScript is determined by *how* a function is called, not where it's defined:

| Call Style | `this` Value |
|-----------|-------------|
| `obj.method()` | `obj` |
| `func()` | `undefined` (strict) or `globalThis` (sloppy) |
| `new Func()` | The new instance |
| `func.call(obj)` / `func.apply(obj)` | `obj` |
| `func.bind(obj)()` | `obj` (permanently) |
| `() => ...` | Inherited from enclosing scope (lexical) |

**Arrow functions don't have their own `this`** — they lexically inherit it. This is why React class component methods need `.bind(this)` but arrow function class properties don't:

```javascript
class Old extends React.Component {
  constructor(props) {
    super(props);
    this.handleClick = this.handleClick.bind(this); // manual binding
  }
  handleClick() { /* `this` is the component */ }
}

class Modern extends React.Component {
  handleClick = () => { /* arrow inherits `this` from class body */ };
}
```

In functional React (hooks), `this` is irrelevant — closures replace it entirely.

## 4. Async Patterns

### Promises

```javascript
fetch('/api/orders/')
  .then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then(data => render(data))
  .catch(err => showError(err));  // catches any error in the chain
```

**Promise states**: pending → fulfilled OR rejected. Once settled, a promise never changes state.

**Error propagation**: An error in any `.then` skips to the nearest `.catch`. Missing `.catch` on a rejected promise triggers `unhandledrejection`.

### `async`/`await`

Syntactic sugar over promises. Makes async code read like synchronous:

```javascript
async function loadOrders() {
  try {
    const res = await fetch('/api/orders/');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    showError(err);
  }
}
```

**`return` vs `return await`**: Inside a `try`/`catch`, you must `return await` for the `catch` to intercept rejections. Plain `return` forwards the promise without awaiting.

### Concurrent Waiting

```javascript
// Wait for all — fails fast if any reject
const [users, orders] = await Promise.all([fetchUsers(), fetchOrders()]);

// Wait for all — never rejects, returns status objects
const results = await Promise.allSettled([fetchUsers(), fetchOrders()]);
// [{status: 'fulfilled', value: [...]}, {status: 'rejected', reason: Error}]

// First to settle wins
const fastest = await Promise.race([fetchFromPrimary(), fetchFromFallback()]);

// First to FULFILL wins (ignores rejections unless all reject)
const first = await Promise.any([fetchFromCDN1(), fetchFromCDN2()]);
```

**TanStack Query context**: TanStack Query manages these patterns internally — parallel queries, race conditions from stale requests, and retry logic. Understanding `Promise.all` vs `Promise.allSettled` helps when writing custom query functions.

### AbortController — Cancellation

```javascript
const controller = new AbortController();

fetch('/api/orders/', { signal: controller.signal })
  .then(res => res.json())
  .catch(err => {
    if (err.name === 'AbortError') return; // expected cancellation
    throw err;
  });

// Cancel the request (e.g., on component unmount or new search)
controller.abort();
```

React pattern: create an `AbortController` in a `useEffect` and call `abort()` in the cleanup function. TanStack Query does this automatically for cancelled queries.

## 5. Destructuring, Spread, and Rest

```javascript
// Object destructuring with defaults and rename
const { name, age = 0, address: { city } } = user;

// Array destructuring (common in React hooks)
const [count, setCount] = useState(0);

// Spread — shallow copy (objects and arrays)
const updated = { ...user, name: 'New Name' };  // override one field
const combined = [...arr1, ...arr2];

// Rest — collect remaining
const { id, ...rest } = user;  // rest = everything except id
function log(message, ...args) { console.log(message, args); }
```

**Spread is shallow**: `{ ...obj }` copies one level. Nested objects are still references. For deep cloning, use `structuredClone(obj)` (available in all modern environments).

## 6. Optional Chaining and Nullish Coalescing

```javascript
// Optional chaining — short-circuits to undefined
const city = user?.address?.city;          // property access
const first = users?.[0];                   // array index
const result = user?.getName?.();           // method call

// Nullish coalescing — only null/undefined, not 0 or ''
const port = config.port ?? 3000;           // 0 is a valid port, so ?? not ||
const name = user.name ?? 'Anonymous';      // '' would pass through with ??

// Logical assignment
user.name ??= 'Anonymous';                 // assign only if null/undefined
user.scores ||= [];                        // assign if falsy (including 0, '')
```

**`??` vs `||`**: `||` treats `0`, `''`, `false`, `NaN` as falsy. `??` only triggers on `null`/`undefined`. Use `??` for values where `0` or `''` are meaningful.

## 7. Iterators and Generators

```javascript
// for...of works with any iterable (arrays, strings, Maps, Sets, generators)
for (const item of array) { ... }
for (const [key, value] of map) { ... }
for (const char of string) { ... }

// Generator functions — lazy sequences
function* range(start, end) {
  for (let i = start; i < end; i++) yield i;
}
for (const n of range(0, 5)) console.log(n); // 0, 1, 2, 3, 4

// Async generators — lazy async sequences
async function* fetchPages(url) {
  let next = url;
  while (next) {
    const res = await fetch(next);
    const data = await res.json();
    yield data.results;
    next = data.next; // DRF pagination URL
  }
}

for await (const page of fetchPages('/api/items/')) {
  renderItems(page);
}
```

## 8. Modules (ES Modules)

```javascript
// Named exports
export function add(a, b) { return a + b; }
export const PI = 3.14159;

// Default export
export default class Calculator { ... }

// Importing
import Calculator, { add, PI } from './math.js';
import * as math from './math.js';  // namespace import

// Dynamic import — code splitting
const { Chart } = await import('./chart.js'); // returns a promise
```

**Tree shaking**: Bundlers (Vite/Rollup) eliminate unused named exports from the final bundle. This only works with ES modules (`import`/`export`), not CommonJS (`require`). Default exports are harder to tree-shake than named exports.

**Re-exports** (barrel files):
```javascript
// utils/index.js
export { add, subtract } from './math.js';
export { formatDate } from './dates.js';
```

Barrel files can hurt tree-shaking if the bundler can't determine side-effect-free modules. Vite handles this well with `"sideEffects": false` in `package.json`.

## 9. WeakRef, FinalizationRegistry, and Structured Clone

```javascript
// WeakRef — hold a reference without preventing GC
const weakRef = new WeakRef(largeObject);
const obj = weakRef.deref(); // returns object or undefined if GC'd

// structuredClone — deep clone (replaces JSON.parse(JSON.stringify()))
const deep = structuredClone(complexObject);
// Handles: Date, RegExp, Map, Set, ArrayBuffer, circular refs
// Cannot clone: functions, DOM nodes, symbols

// FinalizationRegistry — callback when object is GC'd
const registry = new FinalizationRegistry((heldValue) => {
  console.log(`Object with key ${heldValue} was collected`);
});
registry.register(object, 'my-key');
```

## Sources

- MDN JavaScript Guide: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide
- MDN Event Loop: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Event_loop
- Jake Archibald — Tasks, Microtasks: https://jakearchibald.com/2015/tasks-microtasks-queues-and-schedules/
- TC39 Finished Proposals: https://github.com/tc39/proposals/blob/main/finished-proposals.md
